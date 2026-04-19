FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build

# Serve with a lightweight web server
RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "3000"]