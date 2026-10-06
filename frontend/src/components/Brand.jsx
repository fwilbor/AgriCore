// AgriCore brand marks, cut from the master logo in /assets.
// Files live in frontend/public/brand/ and are served at /brand/*.
import { Avatar, Box } from '@mui/material'

export const LOGO_FULL = '/brand/agricore-logo.jpg'
export const LOGO_WORDMARK = '/brand/agricore-wordmark.png'
export const LOGO_BADGE = '/brand/agricore-badge.png'

// "AgriCore — Equipment. Service. Insight." wordmark.
// The dark-green "Core" letters need a light surface, so in dark mode the
// wordmark sits on a soft white plate.
export function Wordmark({ width = 180, sx }) {
  return (
    <Box
      sx={[
        { display: 'inline-flex', borderRadius: 2, lineHeight: 0, width, maxWidth: '100%', boxSizing: 'border-box' },
        (theme) => theme.applyStyles('dark', { bgcolor: '#f5f7f1', px: 1.25, py: 0.75 }),
        ...(Array.isArray(sx) ? sx : [sx]),
      ]}
    >
      <Box component="img" src={LOGO_WORDMARK} alt="AgriCore - Equipment. Service. Insight." sx={{ width: '100%', height: 'auto' }} />
    </Box>
  )
}

// Round mascot badge - favicon, avatars, friendly headers.
export function BrandBadge({ size = 40, sx }) {
  return <Avatar src={LOGO_BADGE} alt="AgriCore mascot" sx={{ width: size, height: size, ...sx }} />
}
