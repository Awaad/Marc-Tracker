FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 8099

# Run TS directly (no watch)
CMD ["npx", "tsx", "src/index.ts"]
