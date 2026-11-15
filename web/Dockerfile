FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# notebook (default) or serious: two looks from one code base
ARG VITE_EDITION=notebook
ENV VITE_EDITION=$VITE_EDITION
RUN npm run build

FROM nginx:1.27-alpine
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
