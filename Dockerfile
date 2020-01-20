FROM openjdk:8u212-jdk-alpine

WORKDIR /app

EXPOSE 8080 9090

ENV APP_NAME=spring-boot-demo \
    APP_VERSION=0.0.1-SNAPSHOT

# RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
#     echo "Asia/Shanghai" > /etc/timezone

COPY target/${APP_NAME}-${APP_VERSION}.jar ${APP_NAME}-${APP_VERSION}.jar

ENTRYPOINT java $JAVA_OPTS -Djava.security.egd=file:/dev/./urandom -XX:+PrintFlagsFinal -XX:+UnlockExperimentalVMOptions -XX:+UseCGroupMemoryLimitForHeap -jar ${APP_NAME}-${APP_VERSION}.jar
