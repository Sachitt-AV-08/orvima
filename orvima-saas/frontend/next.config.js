/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: { domains: ['localhost'] },
  output: 'standalone',
  async rewrites() {
    return [
      { source: '/api/backend/:path*', destination: 'http://localhost:8000/api/:path*' },
    ];
  },
};

module.exports = nextConfig;