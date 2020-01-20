import re
import os
import json
import time
import requests
from urllib.parse import urljoin

SALT_URL = os.getenv("DCS_CLUSTER_URL")
SALT_USER = os.getenv("DCS_CLUSTER_USERNAME")
SALT_PWD = os.getenv("DCS_CLUSTER_PASSWORD")
SERVICES = json.loads(os.getenv("DCS_MICRO_SERVICES") or "[]")
NODE_TARGET = "*"

DEFAULT_HEADERS = {
    'User-Agent': "SaltClient/DCS",
    'Accept-Encoding': ', '.join(('gzip', 'deflate')),
    'Accept': '*/*',
    'Connection': 'keep-alive',
}

assert SALT_URL, "Need SaltStack master api url"
assert SALT_USER, "Need SaltStack username"
assert SALT_PWD, "Need SaltStack Password"


class SyncError(RuntimeError):
    pass


class SaltClientError(SyncError):
    pass


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
        return result

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
            raise SaltClientError("Can't get salt token, check your salt master"
                                  " config or salt version.")
        self.headers['X-Auth-Token'] = token
        return True

    def ps_aux(self, node_id):
        data = {
            "tgt": node_id,
            "fun": "cmd.run",
            "client": "local",
            "arg": "ps aux | grep java | grep demo | grep -v entrypoint",
        }
        print("Run {}".format(
            "ps aux | grep java | grep demo | grep -v entrypoint"))
        rsp = self._post(data)
        return rsp['return'][0]


def sync_service(services=SERVICES):
    salt_client = SaltClient()
    print("Login SaltStack.")
    salt_client.login()
    print("start sync all service.")
    ps_result = salt_client.ps_aux(NODE_TARGET)
    for service in services:
        print("sync service {}".format(
            service['service_name'] or service['package_name']))
        sync_instance(service, ps_result)
        print("get service instance {}".format(
            len(service['service_instance'])))


def sync_instance(service, node_pros: dict):
    #pattern = "{}[_a-zA-Z0-9\-]+".format(service['package_name'])
    print(service['package_name'])
    service_instance = []

    for node_name, result in node_pros.items():
        #print(result)
        process = result.split("\n")
        #print(process)
        #print(result)
        has = False
        for p in process:
            mt = service['package_name'] in p
            #print(p)
            print(mt)
            if not mt:
                continue
            has = True
            package = service['package_name']
            service_instance.append({
                "service_instance_id": "{}-{}".format(node_name, package),
                "service_instance_name": node_name,
                "package_name": service['package_name'],
                "release_name": 'spring-boot-demo-0.0.1-SNAPSHOT.jar',
                "status": "running",
            })
        if not has:
            service_instance.append({
                "service_instance_id": "{}-{}".format(node_name, service['package_name']),
                "service_instance_name": node_name,
                "package_name": service['package_name'],
                "release_name": service['release_name'],
                "status": "stopped",
            })
    print(service_instance)
    service['service_instance'] = service_instance


def gen_report():
    report_path = "/report/report.json"
    print("Gen report to {}".format(report_path))
    with open(report_path, "w") as f:
        f.write(json.dumps(dict(micro_services=SERVICES)))
    print("Finish.")


if __name__ == "__main__":
    sync_service()
    gen_report()
    time.sleep(10)