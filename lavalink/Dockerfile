FROM eclipse-temurin:17-jre-jammy
WORKDIR /opt/lavalink
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o Lavalink.jar https://github.com/lavalink-devs/Lavalink/releases/download/4.2.2/Lavalink.jar
COPY application.yml ./application.yml
EXPOSE 2333
CMD ["java", "-Xms128M", "-Xmx384M", "-jar", "Lavalink.jar"]
