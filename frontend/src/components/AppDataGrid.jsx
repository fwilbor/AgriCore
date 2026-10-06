// MUI DataGrid with an always-visible search box.
//
// The search box and the grid share one piece of state - the grid's
// `filterModel`. Typing updates `quickFilterValues`; the grid then filters
// every column live (client-side). Sorting, column filters, CSV export and
// pagination come from the DataGrid toolbar and footer.
import SearchIcon from '@mui/icons-material/Search'
import { Box, Card, InputAdornment, TextField } from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import { useState } from 'react'

export default function AppDataGrid({ searchPlaceholder = 'Search…', pageSize = 10, sx, initialState, ...gridProps }) {
  const [search, setSearch] = useState('')
  const [filterModel, setFilterModel] = useState({ items: [], quickFilterValues: [] })

  function handleSearch(value) {
    setSearch(value)
    setFilterModel((m) => ({ ...m, quickFilterValues: value.split(' ').filter(Boolean) }))
  }

  return (
    <Card>
      <Box sx={{ px: 2, pt: 2 }}>
        <TextField
          size="small"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={searchPlaceholder}
          sx={{ width: { xs: '100%', sm: 360 } }}
          slotProps={{
            input: { type: 'search', startAdornment: <InputAdornment position="start"><SearchIcon /></InputAdornment> },
          }}
        />
      </Box>
      <DataGrid
        filterModel={filterModel}
        onFilterModelChange={(m) => {
          setFilterModel(m)
          setSearch((m.quickFilterValues || []).join(' '))
        }}
        showToolbar
        slotProps={{ toolbar: { showQuickFilter: false } }}
        disableRowSelectionOnClick
        pageSizeOptions={[10, 25, 50, 100]}
        initialState={{ pagination: { paginationModel: { pageSize } }, ...initialState }}
        sx={{ border: 0, minHeight: 400, ...sx }}
        {...gridProps}
      />
    </Card>
  )
}
