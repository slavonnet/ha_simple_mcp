FROM ghcr.io/home-assistant/home-assistant:stable

USER root
RUN mkdir -p /config/custom_components/ha_simple_mcp
COPY custom_components/ha_simple_mcp /config/custom_components/ha_simple_mcp
USER abc
