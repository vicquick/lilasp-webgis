FROM node:20-alpine AS build
WORKDIR /app
COPY package.json yarn.lock* package-lock.json* ./
RUN if [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
    elif [ -f package-lock.json ]; then npm ci; \
    else npm install; fi
COPY . .

ARG WEB_QGIS_BASE=/qgisserver
ARG WEB_TILES_BASE=/tiles
ARG WEB_WHOAMI=/whoami
ARG WEB_SERVICES_JSON_URL=/services.json
ENV WEB_QGIS_BASE=$WEB_QGIS_BASE \
    WEB_TILES_BASE=$WEB_TILES_BASE \
    WEB_WHOAMI=$WEB_WHOAMI \
    WEB_SERVICES_JSON_URL=$WEB_SERVICES_JSON_URL

RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
