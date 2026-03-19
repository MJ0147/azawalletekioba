const http = require("http");

const port = Number(process.env.PORT) || 8080;

const server = http.createServer((request, response) => {
  response.writeHead(200, { "Content-Type": "application/json" });
  response.end(
    JSON.stringify({
      status: "ok",
      service: "node-frontend",
      path: request.url,
    })
  );
});

server.listen(port, () => {
  console.log(`Frontend server listening on port ${port}`);
});