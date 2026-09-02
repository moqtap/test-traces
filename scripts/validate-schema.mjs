#!/usr/bin/env node
import { readFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);

const schema = JSON.parse(
  readFileSync("schema/moqtrace-manifest.schema.json", "utf8"),
);
const validate = ajv.compile(schema);

const manifest = JSON.parse(readFileSync("moqtrace/manifest.json", "utf8"));

if (validate(manifest)) {
  console.log(
    `Schema validation: moqtrace/manifest.json passed, ${manifest.cases.length} cases`,
  );
  process.exit(0);
}

console.error("FAIL: moqtrace/manifest.json");
for (const err of validate.errors) {
  console.error(`  ${err.instancePath} ${err.message}`);
}
process.exit(1);
