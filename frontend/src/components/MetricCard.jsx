import { Box, Card, CardContent, Typography } from '@mui/material'

export default function MetricCard({ label, value, caption, icon, tone = 'primary' }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Typography variant="body2" color="text.secondary" fontWeight={600}>
            {label}
          </Typography>
          <Box sx={{ color: `${tone}.main`, display: 'flex' }}>{icon}</Box>
        </Box>
        <Typography variant="h4" sx={{ mt: 1, fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </Typography>
        {caption && (
          <Typography variant="caption" color="text.secondary">
            {caption}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}
