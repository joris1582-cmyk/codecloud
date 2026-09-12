FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install --production

# Copy application files
COPY . .

# Ensure storage and upload directories exist
RUN mkdir -p storage temp_uploads

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3050

EXPOSE 3050

CMD ["node", "server.js"]
