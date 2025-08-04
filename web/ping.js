const express = require('express');
const schedule = require('node-schedule');
const sendMorningReport = require('../tasks/morningReport'); // ← đúng đường dẫn

const app = express();
const port = process.env.PORT || 3000;

// Trang ping để Render giữ bot sống
app.get('/', (req, res) => {
  res.send('🤖 Cofure bot đang hoạt động và sẵn sàng gửi tín hiệu!');
});

app.listen(port, () => {
  console.log(`🌐 Web server đang chạy tại cổng ${port} để giữ bot sống.`);
});

// Lịch gửi bản tin 6h sáng (giờ VN) → 23h UTC hôm trước
schedule.scheduleJob('0 23 * * *', () => {
  console.log('🕕 Đang gửi bản tin sáng (06:00)...');
  sendMorningReport();
});
