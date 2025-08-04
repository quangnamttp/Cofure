const TelegramBot = require('node-telegram-bot-api');
const { TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, TIMEZONE } = require('./config');
const dayjs = require('dayjs');
require('dayjs/locale/vi');
dayjs.locale('vi');

const bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });
console.log('🤖 Cofure bot đã khởi động!');

global.bot = bot;
global.USER_IDS = TELEGRAM_USER_IDS;

require('./web');

// Tạm thời chưa load tasks vì bạn chưa tạo thư mục `tasks/`
