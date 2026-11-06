# Website deployment / Triển khai trang giới thiệu

The English landing page is a static website in `docs/`. It has no package installation or JavaScript build step. Images are rendered from the application's own character geometry; no third-party stock artwork or external fonts are used.

## Preview locally

From the project directory:

```powershell
python -m http.server 8080 --directory docs
```

Open `http://localhost:8080`. Stop the preview server with Ctrl+C.

## Publish with GitHub Pages

1. Push the website files to `main`.
2. Open repository **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select **main**, choose **/docs**, then **Save**.
5. Wait for the Pages deployment to complete and use the URL GitHub displays.

Expected URL: `https://vynnvu.github.io/VynnNotifyQPainter/`.

Publishing is not enabled merely by adding the files. Repository settings must be configured by someone with the required permissions. See [GitHub's publishing-source instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Search metadata

The site includes an English title and description, canonical URL, social sharing metadata, SoftwareApplication structured data, `robots.txt` and `sitemap.xml`. These help describe the page; they do not guarantee indexing or ranking.

If changing the repository name or using a custom domain, update the canonical URL, Open Graph URLs, structured-data URL, `robots.txt` and `sitemap.xml` together. Add the live site to your repository's About/Website field after deployment. You can submit the sitemap in a search-engine webmaster tool you control.

## Keep claims accurate

The app currently uses Vietnamese controls; the page and English guide say so explicitly. Do not remove that notice until English UI is implemented. The download is approximately 31 MB, not a measurement of RAM. No fake ratings, testimonials, donation links or health claims are included.

## Tiếng Việt

Chạy lệnh xem thử ở trên để mở trang trên máy. Để xuất bản, vào **Settings → Pages → Deploy from a branch → main → /docs → Save**. URL dự kiến chỉ hoạt động sau khi bật Pages và triển khai thành công.

Trang dùng ảnh Vynn thật, có bố cục cho điện thoại và máy tính, nút tải bản Lite, hướng dẫn nhanh, FAQ và thông tin cho công cụ tìm kiếm. Khi đổi tên repo hoặc tên miền, cần sửa đồng bộ các URL SEO đã liệt kê.
