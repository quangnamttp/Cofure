// web/ping.js
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

// Khởi động toàn bộ bot (gồm schedule, Telegram, gửi tín hiệu...)
require('../index');

app.get('/', (req, res) => {
  res.send('🤖 Cofure bot đang hoạt động & ping giữ cho Render sống!');
});

app.listen(port, () => {
  console.log(`🌐 Ping server đang chạy tại cổng ${port} – giữ bot luôn sống`);
});
