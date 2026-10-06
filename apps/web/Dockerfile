FROM node:24-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY components ./components
COPY lib ./lib
COPY types ./types
COPY tsconfig.json next-env.d.ts eslint.config.mjs ./
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build --chown=node:node /app/.next ./.next
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
