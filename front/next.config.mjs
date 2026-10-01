/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    unoptimized: true,
  },
  async rewrites() {
    const target = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000'
    return [{ source: '/api/:path*', destination: `${target}/api/:path*` }]
  },
}

export default nextConfig
