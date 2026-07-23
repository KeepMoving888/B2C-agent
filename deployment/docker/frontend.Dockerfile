FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package*.json ./
# 若无 package.json，跳过 npm install
RUN if [ -f package.json ]; then npm install; fi

FROM nginx:alpine
COPY frontend/ /usr/share/nginx/html
COPY deployment/docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
