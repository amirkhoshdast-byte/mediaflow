FROM node:22-alpine
WORKDIR /app
RUN echo 'require("http").createServer((q,r)=>r.end("web placeholder")).listen(3000)' > s.js
CMD ["node","s.js"]
