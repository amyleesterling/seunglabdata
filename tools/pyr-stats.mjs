// Refreshes "Pyr by the numbers" on pyr/index.html from GitHub's public record
// for seung-lab/ng-extend, branch eyewire-ii-community:
//   commits = every commit on the branch,
//   updates = successful runs of on_dev_branch_push.yml (each one deploys the game),
//   chart   = those runs per week (weeks start Monday, UTC).
// Run weekly by .github/workflows/pyr-stats.yml. Set GITHUB_TOKEN to avoid rate limits.
import { readFileSync, writeFileSync } from 'node:fs';

const REPO = 'seung-lab/ng-extend';
const BRANCH = 'eyewire-ii-community';
const WORKFLOW = 'on_dev_branch_push.yml';
const START = '2026-03-01'; // GitHub's deploy record for Pyr starts in March 2026
const PAGE = new URL('../pyr/index.html', import.meta.url);

const headers = { Accept: 'application/vnd.github+json', 'User-Agent': 'connectome-quest-pyr-stats' };
if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;

async function get(path) {
  const res = await fetch('https://api.github.com' + path, { headers });
  if (!res.ok) throw new Error(`${res.status} ${path}: ${await res.text()}`);
  return res;
}

async function commitCount() {
  const res = await get(`/repos/${REPO}/commits?sha=${BRANCH}&per_page=1`);
  const m = /[?&]page=(\d+)>; rel="last"/.exec(res.headers.get('link') || '');
  if (!m) throw new Error('no commit count in the Link header');
  return Number(m[1]);
}

// The runs search stops at 1000 results, so ask one month at a time.
async function deployDates() {
  const dates = [];
  const now = new Date();
  for (let d = new Date(START + 'T00:00:00Z'); d < now; d.setUTCMonth(d.getUTCMonth() + 1)) {
    const from = d.toISOString().slice(0, 10);
    const next = new Date(d); next.setUTCMonth(next.getUTCMonth() + 1);
    const to = new Date(next - 86400000).toISOString().slice(0, 10);
    for (let page = 1; ; page++) {
      const res = await get(`/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?branch=${BRANCH}&status=success&per_page=100&page=${page}&created=${from}..${to}`);
      const { workflow_runs: runs, total_count: total } = await res.json();
      if (total >= 1000) throw new Error(`${from}: ${total} runs, over the search limit; split the month`);
      runs.forEach(r => dates.push(r.created_at));
      if (runs.length < 100) break;
    }
  }
  return dates;
}

function monday(iso) {
  const d = new Date(iso.slice(0, 10) + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d;
}

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const nice = d => `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;

const [commits, dates] = await Promise.all([commitCount(), deployDates()]);
if (!dates.length || commits < 1000) throw new Error(`numbers look wrong: ${commits} commits, ${dates.length} updates`);

const counts = new Map();
dates.forEach(t => { const k = monday(t).toISOString().slice(0, 10); counts.set(k, (counts.get(k) || 0) + 1); });
const first = [...counts.keys()].sort()[0];
const weeks = [];
for (let d = new Date(first + 'T00:00:00Z'), end = monday(new Date().toISOString()); d <= end; d.setUTCDate(d.getUTCDate() + 7)) {
  const k = d.toISOString().slice(0, 10);
  weeks.push([k, counts.get(k) || 0]);
}
const peak = weeks.reduce((a, b) => (b[1] > a[1] ? b : a));
const today = new Date();
const year = today.getUTCFullYear();
const fmt = n => n.toLocaleString('en-US');

let s = readFileSync(PAGE, 'utf8');
const before = s;
function sub(re, to) {
  if (!re.test(s)) throw new Error('not found on the page: ' + re);
  s = s.replace(re, to);
}
sub(/Numbers counted \d{4}-\d\d-\d\d/, `Numbers counted ${today.toISOString().slice(0, 10)}`);
sub(/<b>[\d,]+<\/b><span>commits to Pyr's code/, `<b>${fmt(commits)}</b><span>commits to Pyr's code`);
sub(/<b>[\d,]+<\/b><span>updates sent live since March/, `<b>${fmt(dates.length)}</b><span>updates sent live since March`);
sub(/aria-label="Bar chart of updates sent live each week from March to [^"]*"/,
  `aria-label="Bar chart of updates sent live each week from March to ${MONTHS[today.getUTCMonth()]} ${year}. Busiest week: ${peak[1]} updates, the week of ${nice(new Date(peak[0] + 'T00:00:00Z'))}."`);
sub(/Counted [A-Z][a-z]+ \d+, \d{4} from GitHub/, `Counted ${nice(today)}, ${year} from GitHub`);
sub(/var weeks = \[.*\];/, `var weeks = ${JSON.stringify(weeks)};`);

if (s !== before) writeFileSync(PAGE, s);
console.log(`${fmt(commits)} commits, ${fmt(dates.length)} updates, ${weeks.length} weeks, busiest ${peak[0]} (${peak[1]})`);
