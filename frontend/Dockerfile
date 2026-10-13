FROM node:lts-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG API_URL
ENV API_URL=$API_URL
RUN npm run build


FROM nginx:alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /app/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]