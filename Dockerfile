
FROM node:18-slim

WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY . .

RUN npm install

EXPOSE 3005

CMD ["node","app.js"]
