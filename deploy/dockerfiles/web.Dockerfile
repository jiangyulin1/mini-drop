# Mini-Drop Web 前端构建与部署
FROM node:20-alpine AS build

WORKDIR /app
COPY web/package.json ./
RUN npm install

COPY web/ ./
RUN npm run build

FROM nginx:alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
