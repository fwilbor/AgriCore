import { Box, LinearProgress, Typography } from '@mui/material'

// Fuel gauge for grids: red under 20%, amber under 40%, green otherwise.
export default function FuelBar({ value }) {
  const color = value < 20 ? 'error' : value < 40 ? 'warning' : 'success'
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%', height: '100%' }}>
      <LinearProgress
        variant="determinate"
        value={value}
        color={color}
        sx={{ flex: 1, height: 8, borderRadius: 4 }}
      />
      <Typography variant="body2" sx={{ minWidth: 44, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
        {value.toFixed(1)}%
      </Typography>
    </Box>
  )
}
