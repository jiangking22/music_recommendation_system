FROM node:24-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY tsconfig.json next-env.d.ts eslint.config.mjs ./
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
