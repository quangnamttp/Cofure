// web.js
const express = require('express');
const app = express();

app.get('/', (req, res) => {
  res.send('✅ Cofure bot vẫn đang hoạt động!');
});

app.listen(process.env.PORT || 3000, () => {
  console.log('🌐 Web server đang chạy để giữ bot sống!');
});
