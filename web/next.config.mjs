/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Разрешаем картинки/видео из Replicate и Meta CDN
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.replicate.delivery" },
      { protocol: "https", hostname: "**.fbcdn.net" },
    ],
  },
};

export default nextConfig;
