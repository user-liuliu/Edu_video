# 第一阶段：构建前端静态文件
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# package-lock.json 里的 resolved 地址已经指向 registry.npmmirror.com
RUN npm ci --registry=https://registry.npmmirror.com
COPY . .
RUN npm run build

# 第二阶段：nginx 托管 dist，并把 /api/ 转发给后端
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
