FROM node:24-alpine

WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY components ./components
COPY lib ./lib
COPY types ./types
COPY tsconfig.json next-env.d.ts eslint.config.mjs ./
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
