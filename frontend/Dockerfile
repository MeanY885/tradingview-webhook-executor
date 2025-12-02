# Build stage
FROM node:18 AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build arguments for environment variables
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# Production stage - use nginx to serve
FROM nginx:alpine

# Copy built files from builder to a temp location
COPY --from=builder /app/dist /app-dist

# Create entrypoint script to copy files to volume
RUN echo -e '#!/bin/sh\n\
if [ ! -f /usr/share/nginx/html/index.html ] || [ "$(ls -A /usr/share/nginx/html | wc -l)" -lt 3 ]; then\n\
  echo "Copying frontend build to volume..."\n\
  cp -r /app-dist/* /usr/share/nginx/html/\n\
  echo "Frontend build copied successfully"\n\
fi\n\
exec nginx -g "daemon off;"' > /docker-entrypoint-custom.sh \
  && chmod +x /docker-entrypoint-custom.sh

EXPOSE 80

CMD ["/docker-entrypoint-custom.sh"]
