/** @type {import('next').NextConfig} */
module.exports = {
  output: "export",  // static export for Cloudflare Pages
  trailingSlash: true,
  images: { unoptimized: true },
};
