const {defineConfig} = require('@playwright/test')
module.exports = defineConfig({testDir:'./e2e',timeout:180000,expect:{timeout:15000},workers:1,use:{baseURL:'http://127.0.0.1:5174',headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome',screenshot:'only-on-failure'},reporter:'list'})
