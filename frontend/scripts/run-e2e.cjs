// The CJS suite needs no ESM loader. Avoid the old Playwright TS loader's Node 24 hang.
const {spawnSync}=require('node:child_process')
const result=spawnSync(process.execPath,[require.resolve('@playwright/test/cli'),'test',...process.argv.slice(2)],{stdio:'inherit',env:{...process.env,PW_DISABLE_TS_ESM:'1'}})
process.exit(result.status??1)
