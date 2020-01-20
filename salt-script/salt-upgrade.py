import os
import time
import json
import requests
from urllib.parse import urljoin

# DCS Default env
SALT_URL = os.getenv("DCS_CLUSTER_URL")
SALT_USER = os.getenv("DCS_CLUSTER_USERNAME")
SALT_PWD = os.getenv("DCS_CLUSTER_PASSWORD")
INSTANCE_NAME = os.getenv("DCS_INSTANCE_NAME")
CLUSTER_ENV = os.getenv("DCS_CLUSTER_ENV")
SERVICES = json.loads(os.getenv("DCS_MICRO_SERVICES") or "[]")

TARGET_HOME = os.getenv("TARGET_HOME", "/root")
TMP_HOME = os.getenv("TMP_HOME", "/tmp")
ENTRYPOINT_URL = 'http://192.168.150.72/file/demo/spring-boot-sample/salt-entrypoint.sh'

assert SALT_URL, "Need SaltStack master api url"
assert SALT_USER, "Need SaltStack username"
assert SALT_PWD, "Need SaltStack Password"
assert INSTANCE_NAME, "Can't get instance name"


class DeployError(Exception):
    pass


class SaltClientError(DeployError):
    pass


class Service:
    def __init__(self, package_name, release_name, path, token):
        self.package_name = package_name
        self.release_name = release_name
        self.path = path
        self.token = token


DEFAULT_HEADERS = {
    'User-Agent': "SaltClient/DCS",
    'Accept-Encoding': ', '.join(('gzip', 'deflate')),
    'Accept': '*/*',
    'Connection': 'keep-alive',
}


def print_result(result, index=0):
    if isinstance(result, list):
        for r in result:
            print_result(r, index + 1)
        return
    if isinstance(result, dict):
        for k, v in result.items():
            print("|" + "--" * index + str(k))
            print_result(v, index + 1)
        return
    result = str(result)
    result = result.split('\n')
    result = str("\n|" + "--" * index).join(result)
    print("|" + "--" * index + str(result))


class SaltClient(requests.Session):
    def __init__(self):
        super(SaltClient, self).__init__()
        self.base_url = SALT_URL
        self.verify = False
        self.eauth = "pam"
        self.headers = DEFAULT_HEADERS
        self.username = SALT_USER
        self.password = SALT_PWD

    def url(self, path):
        return urljoin(self.base_url, path)

    def _post(self, data):
        try:
            rsp = self.post(self.base_url, json=data, timeout=60)
        except requests.exceptions.RequestException:
            raise SaltClientError("Can't get a connection to {}"
                                  .format(self.base_url))
        status_code = rsp.status_code
        if status_code // 100 != 2:
            msg = "[Status Code {}]: {}".format(status_code, rsp.text)
            raise SaltClientError(msg)
        result = rsp.json()
        print("Salt api return: ")
        print_result(result['return'])
        return result['return']

    def login(self):
        data = {
            "username": self.username,
            "password": self.password,
            "eauth": self.eauth,
        }
        try:
            rsp = self.post(self.url('/login'), json=data, timeout=30)
        except requests.exceptions.RequestException:
            raise SaltClientError("Can't get a connection to {}"
                                  .format(self.base_url))
        if rsp.status_code // 100 != 2:
            if rsp.status_code == 401:
                raise SaltClientError("Username or password error")
            raise SaltClientError("Can't get a connection to {}"
                                  .format(self.base_url))

        try:
            result = rsp.json()['return']
            if len(result) < 1:
                raise SaltClientError(
                    "Can't get salt token, check your master config.")
            token_info = result[0]
            token = token_info['token']
        except (KeyError, ValueError):
            raise SaltClientError(
                "Can't get salt token, check your salt master"
                " config or salt version.")
        self.headers['X-Auth-Token'] = token
        return True

    def async_task(self, node_id, cmd):
        data = {
            "tgt": node_id,
            "fun": "cmd.run",
            "client": "local_async",
            "arg": cmd,
        }
        print("Run {}".format(cmd))
        rsp = self._post(data)
        return rsp[0]['jid']

    def wait_async_task(self, node_id, task_id):
        data = {"client": "runner", "fun": "jobs.lookup_jid", "jid": task_id}
        while True:
            rsp = self._post(data)
            if node_id in rsp[0]:
                break
            time.sleep(5)

    def cmd_task(self, node_id, cmd):
        data = {
            "tgt": node_id,
            "fun": "cmd.run",
            "client": "local",
            "arg": cmd,
        }
        print("Run {}".format(cmd))
        rsp = self._post(data)
        return rsp[0][node_id]


class DeployManager:

    def __init__(self, instance_name):
        print("Deploy instance {}".format(instance_name))
        self.salt_client = SaltClient()
        self.services = self._get_services()
        self.nodes = self._get_nodes()

        self.target_path = os.path.join(TARGET_HOME, INSTANCE_NAME,
                                        "{package_name}")
        self.tmp_path = os.path.join(TMP_HOME, INSTANCE_NAME, "{package_name}")
        print("Get {} services".format(len(self.services)))

    def get_shell(self):
        print("Login SaltStack master")
        self.salt_client.login()
        for n in self.nodes:
            for s in self.services:
                package_target_path = self.target_path.format(
                    package_name=s.package_name)
                self.salt_client.cmd_task(
                    n, "mkdir -p {}".format(package_target_path))
                get_shell_cmd = "wget {}?token={} -O {}/salt-entrypoint.sh".format(ENTRYPOINT_URL,
                    s.token, package_target_path)
                self.salt_client.cmd_task(n, get_shell_cmd)
                chmod_shell_cmd = "chmod +x {}/salt-entrypoint.sh".format(
                    package_target_path)
                self.salt_client.cmd_task(n, chmod_shell_cmd)

    def upgrade(self):
        for n in self.nodes:
            for s in self.services:
                package_target_path = self.target_path.format(
                    package_name=s.package_name)
                updrade_shell_cmd = "{work_dir}/salt-entrypoint.sh --method upgrade --name {app_name}.jar --app-url {app_url} --token {token} --work-dir {work_dir} --app-path {work_dir}" \
                    .format(work_dir=package_target_path, app_name=s.package_name, app_url=s.path, token=s.token)
                self.salt_client.cmd_task(n, updrade_shell_cmd)

    def restart(self):
        for n in self.nodes:
            for s in self.services:
                package_target_path = self.target_path.format(
                    package_name=s.package_name)
                updrade_shell_cmd = "{work_dir}/salt-entrypoint.sh --method restart --name {app_name}.jar --app-url {app_url} --token {token} --work-dir {work_dir} --app-path {work_dir}" \
                    .format(work_dir=package_target_path, app_name=s.package_name, app_url=s.path, token=s.token)
                self.salt_client.cmd_task(n, updrade_shell_cmd)

    def check_deploy_task(self):
        # check java app is alive
        pass

    @staticmethod
    def _get_services():
        services = SERVICES
        result = []
        for s in services:
            package_type = s['package_type']
            package_name = s['package_name']
            image = s['release_path']
            print("Get {} package {}, image: {}".format(package_type,
                                                        package_name, image))
            result.append(Service(
                package_name=s['package_name'],
                release_name=s['release_name'],
                path=s['release_path'],
                token=s['token'],
            ))
        return result

    @staticmethod
    def _get_nodes():
        return ["saltstack-01", "saltstack-02", "saltstack-03"]


if __name__ == "__main__":
    dm = DeployManager(INSTANCE_NAME)
    dm.get_shell()
    dm.upgrade()
