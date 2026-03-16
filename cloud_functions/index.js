import * as functions from "@google-cloud/functions-framework";

functions.http("helloHttp", (req, res) => {
  res.set("Content-Type", "text/plain");

  const name = req.query?.name || req.body?.name || "World";
  res.send(`Hello ${name}!`);
});