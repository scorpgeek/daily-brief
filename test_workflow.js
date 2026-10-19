// Structural check for the workflow, without a YAML dependency.
//
// A malformed workflow fails at run time on GitHub, hours later, with the
// only feedback being a red X in a tab. These assertions are cheap and
// catch the ways it actually breaks: a renamed step, a dropped secret, a
// path filter that stops matching.
const fs = require('fs');
const t = fs.readFileSync('.github/workflows/daily.yml', 'utf8');

const checks = [
  ['name',            /^name:\s*daily brief/m],
  ['push trigger',    /push:\s*$/m],
  ['paths incoming',  /paths:\s*\['incoming\/\*\.pdf'\]/],
  ['manual dispatch', /workflow_dispatch:/],
  ['concurrency',     /concurrency:/],
  ['contents write',  /contents:\s*write/],
  ['checkout',        /actions\/checkout@v4/],
  ['setup-python',    /actions\/setup-python@v5/],
  ['pypdf',           /pip install --quiet pypdf/],
  ['secret key',      /DB_API_KEY:\s*\$\{\{\s*secrets\.DB_API_KEY\s*\}\}/],
  ['secret model',    /DB_MODEL:\s*\$\{\{\s*secrets\.DB_MODEL\s*\}\}/],
  ['secret base',     /DB_API_BASE:\s*\$\{\{\s*secrets\.DB_API_BASE\s*\}\}/],
  ['secret spec',     /DB_PROMPT_B64:\s*\$\{\{\s*secrets\.DB_PROMPT_B64\s*\}\}/],
  ['restores spec',   /base64 -d > PROMPT\.md/],
  ['validates spec',  /grep -q 'DASHBOARD SHAPE' PROMPT\.md/],
  ['errors if absent',/No PROMPT\.md and no DB_PROMPT_B64/],
  ['runs daily.py',   /python daily\.py/],
  ['no-push',         /--no-push/],
  ['commits output',  /git add -A -- phone\.html desk\.html archive/],
  ['summary',         /GITHUB_STEP_SUMMARY/],
];

let bad = 0;
for (const [name, re] of checks) {
  const ok = re.test(t);
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${name}`);
  if (!ok) bad++;
}
console.log(bad ? `\n${bad} failed` : '\nworkflow structure ok');
process.exit(bad ? 1 : 0);