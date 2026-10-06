import { createTheme } from '@mui/material/styles'

// Brand palette sampled from the AgriCore logo (assets/):
//   logo green #367a2c · deep forest #12291b · harvest gold #e4b520
export const BRAND = {
  green: '#367a2c',
  forest: '#12291b',
  gold: '#e4b520',
}

// One theme object styles every MUI component. colorSchemes gives automatic
// light/dark mode that follows the operating-system setting.
const theme = createTheme({
  cssVariables: { colorSchemeSelector: 'media' },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: BRAND.green, dark: '#285d20', contrastText: '#ffffff' },
        secondary: { main: BRAND.gold, contrastText: BRAND.forest },
        text: { primary: '#16261b', secondary: '#55625a' },
        background: { default: '#f5f7f1', paper: '#ffffff' },
      },
    },
    dark: {
      palette: {
        primary: { main: '#7fc66f', contrastText: BRAND.forest },
        secondary: { main: '#f0c64a', contrastText: BRAND.forest },
        background: { default: '#0f1a12', paper: '#16241a' },
      },
    },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 800, letterSpacing: '-0.02em' },
    h5: { fontWeight: 800, letterSpacing: '-0.01em' },
    h6: { fontWeight: 600 },
  },
  components: {
    MuiCard: { defaultProps: { variant: 'outlined' } },
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
  },
})

export default theme
