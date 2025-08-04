const express = require('express');
const schedule = require('node-schedule');
const tzOffset = require('tz-offset');
const sendMorningReport = require('./tasks/morningReport'); // ← đúng đường dẫn
const { bot } = require('./web');

const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send('🤖 Cofure bot đang chạy!');
});

// giữ cho Render không tắt app
app.listen(port, () => {
  console.log(`🌐 Web server đang chạy để giữ bot sống!`);
});

// ⏰ Lên lịch gửi bản tin lúc 06:00 sáng giờ Việt Nam (Asia/Ho_Chi_Minh)
schedule.scheduleJob({ hour: 6, minute: 0, tz: 'Asia/Ho_Chi_Minh' }, () => {
  sendMorningReport();
});

console.log('🤖 Cofure bot đã khởi động!');
