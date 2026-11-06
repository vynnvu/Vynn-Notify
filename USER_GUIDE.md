# Hướng dẫn sử dụng Vynn Notify

## 1. Tải và mở ứng dụng

1. Tải [Vynn_Notify_Lite.exe](https://github.com/vynnvu/VynnNotifyQPainter/raw/refs/heads/main/dist/Vynn_Notify_Lite.exe).
2. Lưu vào một thư mục riêng và mở file. Không cần cài Python.
3. Chờ vài giây để Vynn xuất hiện. Bảng điều khiển không tự mở khi khởi động.

Bản EXE hiện được đóng gói cho Windows 64-bit. Nếu Windows hiển thị cảnh báo về nhà phát hành, kiểm tra đúng nguồn tải và chỉ chạy khi bạn tin tưởng nguồn đó; không cần tắt phần mềm bảo vệ máy.

## 2. Tương tác nhanh

| Thao tác | Kết quả |
| --- | --- |
| Bấm nhanh vào Vynn | Đập tay một lần về vị trí chuột lúc bấm |
| Giữ chuột trái khoảng 0,2 giây | Vynn bám chuột, sẵn sàng kéo |
| Giữ và kéo, sau đó thả | Di chuyển Vynn; nhân vật đáp hoặc rơi xuống bề mặt phù hợp |
| Chuột phải vào Vynn | Mở menu hành động |
| Bấm biểu tượng Vynn ở khay hệ thống cạnh đồng hồ | Mở bảng điều khiển |
| Chuột phải biểu tượng khay | Mở các điều khiển nhanh và lệnh thoát |

Nếu chưa thấy biểu tượng, mở vùng biểu tượng ẩn cạnh đồng hồ Windows. Nhấp đúp vào Vynn không dùng để nhảy; chọn **Nhảy** trong menu.

## 3. Menu hành động

- **Đập tay:** đưa tay về vị trí con trỏ tại thời điểm kích hoạt, rồi hạ tay.
- **Nhảy:** nhảy tại chỗ.
- **Tìm chỗ leo:** tự tìm bề mặt phù hợp; có thể đi lấy đà, nhảy bám, leo hoặc tìm đường qua các bề mặt trung gian.
- **Ngủ:** nằm ngang, quay lưng và thể hiện động tác ngủ kiểu pixel.
- **Hoạt động:** đi bộ, ngồi nghỉ, quan sát, vuốt tóc, vươn vai, nhảy múa, buồn hoặc ngồi thiền.
- **Gọi lại:** đi về phía vị trí ngang của con trỏ, trong phạm vi có thể di chuyển.

Menu thay đổi theo trạng thái: đang ngủ có **Đánh thức**, đang leo có **Dừng leo**, đang thiền có **Dừng thiền**. Khi dừng leo, Vynn buông và rơi theo trọng lực.

Không phải vật thể nào trên màn hình cũng leo được. Khi chưa tìm thấy đường an toàn, thử di chuyển Vynn hoặc thay đổi vị trí cửa sổ. Kéo cửa sổ đang đỡ Vynn có thể khiến nhân vật mất chỗ đứng và rơi.

## 4. Bảng điều khiển

Mở từ biểu tượng khay hệ thống. Các thay đổi được áp dụng ngay và tự lưu.

### Tab Vynn

- Chọn kích thước **Rất nhỏ, Nhỏ, Vừa, Lớn**.
- Chọn hoạt động và bấm **Thực hiện**.
- Bật **Tự đi lại** để Vynn tự chọn hoạt động khi rảnh.
- Bật **Đứng yên** để ngừng tự đi lại.
- Bật **Tạm dừng** để dừng chuyển động và trọng lực.
- Bật **Bám bề mặt** để sử dụng các bề mặt được nhận diện.
- Chỉnh tốc độ và khoảng nghỉ giữa các động tác.

Rê chuột lên các tùy chọn để xem chú thích khi cần.

### Tab Nhắc nhở

- Bật/tắt **Nghỉ mắt, Giãn cơ, Uống nước**, rồi đặt chu kỳ theo phút.
- Bấm **Tập trung 25 phút** để bắt đầu; kết thúc phiên sẽ có thời gian nghỉ 5 phút.
- Chọn thời gian thiền rồi bấm **Bắt đầu thiền** để vào chế độ có hẹn giờ.

Trong chế độ thiền hoặc tập trung, thao tác di chuyển bị khóa. Dùng nút dừng tương ứng để kết thúc sớm. Hoạt động **Ngồi thiền** trong danh sách chỉ là động tác, khác với chế độ thiền hẹn giờ.

### Tab Cài đặt

- Chọn **Mở cùng Windows** nếu muốn tự khởi động.
- Chọn **Ẩn khi toàn màn hình** nếu muốn Vynn tạm ẩn khi chơi game hoặc xem nội dung toàn màn hình được ứng dụng nhận diện.
- Bật/tắt lời thoại, chỉnh cỡ chữ, thời gian hiện, chiều rộng và giao diện sáng/tối.
- Tùy chỉnh nội dung từng loại lời thoại và bấm xem thử.

Đóng bảng điều khiển vẫn để Vynn tiếp tục chạy. Muốn tắt ứng dụng, chọn **Thoát Vynn Notify**.

## 5. Dữ liệu và cập nhật

Thiết lập và trạng thái được lưu tại `%APPDATA%\Vynn Notify`. Có thể sao lưu thư mục này trước khi cập nhật hoặc đổi máy.

Để cập nhật bản EXE: thoát Vynn từ khay hệ thống, tải bản mới rồi thay file cũ. Chạy lại bản mới sẽ tiếp tục sử dụng thiết lập đã lưu. Không chạy đồng thời hai bản.

Nếu dùng mã nguồn, `run.bat` dừng phiên được nhận diện trước đó rồi khởi động lại. Hành vi này không có nghĩa là mọi file EXE tải xuống sẽ tự thay thế phiên cũ.

## 6. Khi gặp vấn đề

| Hiện tượng | Cách kiểm tra |
| --- | --- |
| Không thấy Vynn | Kiểm tra biểu tượng khay, tùy chọn ẩn và ứng dụng toàn màn hình |
| Không kéo được | Giữ đủ 0,2 giây; kiểm tra chế độ thiền hoặc tập trung |
| Không di chuyển | Kiểm tra Tự đi lại, Đứng yên và Tạm dừng |
| Không leo được | Bật Bám bề mặt; thử cửa sổ khác hoặc vị trí khác |
| Không thấy lời nhắc | Bật lời thoại và loại nhắc tương ứng; kiểm tra chu kỳ đã đặt |
| Mở ứng dụng hơi lâu | Chờ giải nén tài nguyên, đặc biệt ở lần chạy đầu |

Gửi lỗi tại [GitHub Issues](https://github.com/vynnvu/VynnNotifyQPainter/issues), kèm phiên bản Windows, tên file EXE, các bước gây lỗi và ảnh/video nếu có. Không gửi dữ liệu cá nhân hoặc nội dung cửa sổ nhạy cảm.
