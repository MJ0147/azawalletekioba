FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN npm run build

ENV HOSTNAME=0.0.0.0
ENV PORT=3000

CMD ["npm", "run", "start"]