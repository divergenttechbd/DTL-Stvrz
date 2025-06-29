import { useCallback, useEffect, useState } from 'react';
// @mui
import Badge from '@mui/material/Badge';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
// types
import { IListingFilters, ITourFilterValue } from 'src/types/listing';
// components
import {
  Autocomplete,
  FormControl,
  InputLabel,
  MenuItem,
  OutlinedInput,
  Radio,
  Select,
  SelectChangeEvent,
  TextField,
} from '@mui/material';
import InputAdornment from '@mui/material/InputAdornment';
import startCase from 'lodash/startCase';
import Iconify from 'src/components/iconify';
import Scrollbar from 'src/components/scrollbar';
import { IUserItem } from 'src/types/user';
import { getUsers } from 'src/utils/queries/users';
import { getDistrictPoints, getSubDistrictPoints } from 'src/utils/queries/listing';

const verificationOptions = [
  { label: 'Verified', value: 'verified' },
  { label: 'Unerified', value: 'unverified' },
];

const statusOption = [
  { value: 'in_progress', label: 'In progress' },
  { value: 'unpublished', label: 'Unpublished' },
  { value: 'published', label: 'Published' },
  { value: 'rejected', label: 'Rejected' },
];

type TourFilterProps = {
  open: boolean;
  onOpen: VoidFunction;
  onClose: VoidFunction;
  //
  filters: IListingFilters;
  onFilters: (name: string, value: ITourFilterValue) => void;
  //
  canReset: boolean;
  categoryOptions: { label: string; value: string | number }[];
  onResetFilters: VoidFunction;
  //
  dateError: boolean;
  //
  showHostDropDown?: boolean;
};

type DistrictOption = { label: string; id: number };
type SubDistrictOption = { name: string; lat: number; long: number };

export default function TourFilters({
  open,
  onOpen,
  onClose,
  //
  filters,
  onFilters,
  //
  categoryOptions,
  canReset,
  onResetFilters,
  //
  dateError,
  //
  showHostDropDown = true,
}: TourFilterProps) {
  const [hosts, setHosts] = useState<{ label: string; value: string }[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState<DistrictOption | null>(null);
  // console.log('selected District', selectedDistrict);
  const [subDistrict, setSubDistrict] = useState<any | null>([]);
  const [selectedSubDistrict, setSelectedSubDistrict] = useState<any | null>(null);
  // console.log('subDistrict', subDistrict);

  const options = [
    { label: 'Bagerhat', id: 1 },
    { label: 'Bandarban', id: 2 },
    { label: 'Barguna', id: 3 },
    { label: 'Barisal', id: 4 },
    { label: 'Bhola', id: 5 },
    { label: 'Bogura', id: 6 },
    { label: 'Brahmanbaria', id: 7 },
    { label: 'Chandpur', id: 8 },
    { label: 'Chattogram', id: 9 },
    { label: 'Chuadanga', id: 10 },
    { label: "Cox's Bazar", id: 11 },
    { label: 'Cumilla', id: 12 },
    { label: 'Dhaka', id: 13 },
    { label: 'Dinajpur', id: 14 },
    { label: 'Faridpur', id: 15 },
    { label: 'Feni', id: 16 },
    { label: 'Gaibandha', id: 17 },
    { label: 'Gazipur', id: 18 },
    { label: 'Gopalganj', id: 19 },
    { label: 'Habiganj', id: 20 },
    { label: 'Jamalpur', id: 21 },
    { label: 'Jashore', id: 22 },
    { label: 'Jhalokati', id: 23 },
    { label: 'Jhenaidah', id: 24 },
    { label: 'Joypurhat', id: 25 },
    { label: 'Khagrachari', id: 26 },
    { label: 'Khulna', id: 27 },
    { label: 'Kishoreganj', id: 28 },
    { label: 'Kurigram', id: 29 },
    { label: 'Kushtia', id: 30 },
    { label: 'Lakshmipur', id: 31 },
    { label: 'Lalmonirhat', id: 32 },
    { label: 'Madaripur', id: 33 },
    { label: 'Magura', id: 34 },
    { label: 'Manikganj', id: 35 },
    { label: 'Meherpur', id: 36 },
    { label: 'Moulvibazar', id: 37 },
    { label: 'Munshiganj', id: 38 },
    { label: 'Mymensingh', id: 39 },
    { label: 'Naogaon', id: 40 },
    { label: 'Narail', id: 41 },
    { label: 'Narayanganj', id: 42 },
    { label: 'Narsingdi', id: 43 },
    { label: 'Natore', id: 44 },
    { label: 'Netrokona', id: 45 },
    { label: 'Nilphamari', id: 46 },
    { label: 'Noakhali', id: 47 },
    { label: 'Pabna', id: 48 },
    { label: 'Panchagarh', id: 49 },
    { label: 'Patuakhali', id: 50 },
    { label: 'Pirojpur', id: 51 },
    { label: 'Rajbari', id: 52 },
    { label: 'Rajshahi', id: 53 },
    { label: 'Rangamati', id: 54 },
    { label: 'Rangpur', id: 55 },
    { label: 'Satkhira', id: 56 },
    { label: 'Shariatpur', id: 57 },
    { label: 'Sherpur', id: 58 },
    { label: 'Sirajganj', id: 59 },
    { label: 'Sunamganj', id: 60 },
    { label: 'Sylhet', id: 61 },
    { label: 'Tangail', id: 62 },
    { label: 'Thakurgaon', id: 63 },
    { label: 'Chapainawabganj', id: 64 },
  ];

  // host filter values
  const getHostsForDropdown = useCallback(async () => {
    try {
      const res = await getUsers({ u_type: 'host', page_size: 0 });

      if (!res.success) throw res.data;
      setHosts(
        res.data.map((user: IUserItem) => ({
          label: `${user.full_name} ${user.phone_number}`,
          value: user.id,
        }))
      );
    } catch (err) {
      setHosts([]);
    }
  }, []);
  useEffect(() => {
    getHostsForDropdown();
  }, [getHostsForDropdown]);

  // filters handler
  const handleFilterAreaSearch = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      onFilters('verification_status', event.target.value);
    },
    [onFilters]
  );

  // filters handler
  const handleFilterStartDate = useCallback(
    (newValue: Date | null) => {
      if (newValue?.toString() !== 'Invalid Date') {
        onFilters('created_at_after', newValue);
      }
    },
    [onFilters]
  );

  const handleFilterEndDate = useCallback(
    (newValue: Date | null) => {
      if (newValue?.toString() !== 'Invalid Date') {
        onFilters('created_at_before', newValue);
      }
    },
    [onFilters]
  );

  const handleVerificationChange = useCallback(
    (event: SelectChangeEvent<string>) => {
      onFilters('verification_status', event.target.value);
    },
    [onFilters]
  );

  const handleListingType = useCallback(
    (event: SelectChangeEvent<string>) => {
      onFilters('category', event.target.value);
    },
    [onFilters]
  );

  const handleStatusChange = useCallback(
    (event: SelectChangeEvent<string>) => {
      onFilters('status', event.target.value);
    },
    [onFilters]
  );

  const handleFilterService = useCallback(
    (val: any) => {
      onFilters('host', val);
    },
    [onFilters]
  );

  const handleGetDistrictPoints = async (value: { label: string; id: number } | null) => {
    if (!value) return;

    try {
      const res = await getSubDistrictPoints({ q: value.label });
      if (!res.success) throw res.data;
      const coordsData = res.data;
      setSubDistrict(coordsData);
    } catch (err) {
      console.log(err);
    }
  };

  const handleGetAreaResult = useCallback(
    (value: { name: string; lat: any; long: any } | null) => {
      if (!value) return;

      try {
        onFilters('latitude', value.lat);
        onFilters('longitude', value.long);
        onFilters('sort_by', 'nearest');
      } catch (err) {
        console.log(err);
      }
    },
    [onFilters]
  );

  // filters component
  const renderHead = (
    <Stack
      direction="row"
      alignItems="center"
      justifyContent="space-between"
      sx={{ py: 2, pr: 1, pl: 2.5 }}
    >
      <Typography variant="h6" sx={{ flexGrow: 1 }}>
        Filters
      </Typography>
      <Tooltip title="Reset">
        <IconButton
          onClick={() => {
            setSubDistrict([]);
            setSelectedDistrict(null);
            setSelectedSubDistrict(null);
            onResetFilters();
          }}
        >
          <Badge color="error" variant="dot" invisible={!canReset}>
            <Iconify icon="solar:restart-bold" />
          </Badge>
        </IconButton>
      </Tooltip>
      <IconButton onClick={onClose}>
        <Iconify icon="mingcute:close-line" />
      </IconButton>
    </Stack>
  );

  const renderAreaSearch = (
    <FormControl fullWidth>
      <Autocomplete
        fullWidth
        options={options}
        value={selectedDistrict}
        onChange={(event, newValue) => {
          setSelectedDistrict(newValue);
          handleGetDistrictPoints(newValue);
          console.log('Selected district:', newValue); // you can also call a handler here
        }}
        getOptionLabel={(option) => option.label}
        isOptionEqualToValue={(option, value) => option.id === value?.id}
        renderInput={(params) => (
          <TextField
            {...params}
            value={selectedDistrict}
            label="Search Area..."
            variant="outlined"
          />
        )}
        renderOption={(props, option) => <li {...props}>{option.label}</li>}
      />
    </FormControl>
  );

  const renderSubAreaSearch = (
    <FormControl fullWidth>
      <Autocomplete
        fullWidth
        options={subDistrict}
        value={selectedSubDistrict}
        onChange={(event, newValue) => {
          setSelectedSubDistrict(newValue);
          handleGetAreaResult(newValue);
          console.log('Selected sub district:', newValue); // you can also call a handler here
        }}
        getOptionLabel={(option) => option.name}
        isOptionEqualToValue={(option, value) => option.name === value?.name}
        renderInput={(params) => (
          <TextField
            {...params}
            value={selectedSubDistrict}
            label="Search Sub Area..."
            variant="outlined"
          />
        )}
        renderOption={(props, option) => <li {...props}>{option.name}</li>}
      />
    </FormControl>
  );

  const renderDateRange = (
    <Stack>
      <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
        Durations
      </Typography>
      <Stack spacing={2.5}>
        <DatePicker
          label="Start date"
          value={filters.created_at_after}
          onChange={handleFilterStartDate}
        />
        <DatePicker
          label="End date"
          value={filters.created_at_before}
          onChange={handleFilterEndDate}
          slotProps={{
            textField: {
              error: dateError,
              helperText: dateError && 'End date must be later than start date',
            },
          }}
        />
      </Stack>
    </Stack>
  );

  const renderVerification = (
    <FormControl
      sx={{
        flexShrink: 1,
        width: { xs: 1 },
      }}
    >
      <InputLabel>Verification Status</InputLabel>
      <Select
        value={filters.verification_status}
        onChange={handleVerificationChange}
        input={<OutlinedInput label="Verification Status" />}
        renderValue={(selected) => startCase(selected)}
        MenuProps={{
          PaperProps: {
            sx: { maxHeight: 240 },
          },
        }}
      >
        {verificationOptions.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            <Radio
              disableRipple
              size="small"
              checked={filters.verification_status === option.value}
            />
            {option.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );

  const renderListingType = (
    <FormControl
      sx={{
        flexShrink: 1,
        width: { xs: 1 },
      }}
    >
      <InputLabel>Listing Type</InputLabel>
      <Select
        value={filters.category?.toString()}
        onChange={handleListingType}
        input={<OutlinedInput label="Listing Type" />}
        renderValue={(selected) =>
          categoryOptions.find((opt) => opt.value?.toString() === selected.toString())?.label
        }
        MenuProps={{
          PaperProps: {
            sx: { maxHeight: 240 },
          },
        }}
      >
        {categoryOptions.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            <Radio disableRipple size="small" checked={filters.category === option.value} />
            {option.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );

  const renderStatus = (
    <FormControl
      sx={{
        flexShrink: 0,
        width: { xs: 1 },
      }}
    >
      <InputLabel>Status</InputLabel>
      <Select
        value={filters.status}
        onChange={handleStatusChange}
        input={<OutlinedInput label="Status" />}
        renderValue={(selected) => startCase(selected)}
        MenuProps={{
          PaperProps: {
            sx: { maxHeight: 240 },
          },
        }}
      >
        {statusOption.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            <Radio disableRipple size="small" checked={filters.status === option.value} />
            {option.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );

  const renderHostFilter = (
    <FormControl fullWidth>
      <Autocomplete
        onChange={(event, newValue) => {
          handleFilterService(newValue);
        }}
        value={filters.host ? filters.host : null}
        fullWidth
        options={hosts}
        getOptionLabel={(option) => option.label}
        renderInput={(params) => (
          <TextField
            {...params}
            value={filters.host?.label}
            label="Select Host"
            variant="outlined"
          />
        )}
        renderOption={(props, option, { inputValue }) => <li {...props}>{option.label}</li>}
      />
    </FormControl>
  );

  return (
    <>
      <Button
        disableRipple
        color="inherit"
        endIcon={
          <Badge color="error" variant="dot" invisible={!canReset}>
            <Iconify icon="ic:round-filter-list" />
          </Badge>
        }
        onClick={onOpen}
      >
        Filters
      </Button>

      <Drawer
        anchor="right"
        open={open}
        onClose={onClose}
        slotProps={{
          backdrop: { invisible: true },
        }}
        PaperProps={{
          sx: { width: 280 },
        }}
      >
        {renderHead}

        <Divider />

        <Scrollbar sx={{ px: 2.5, py: 3 }}>
          <Stack spacing={3}>
            {renderAreaSearch}
            {renderSubAreaSearch}
            {renderDateRange}
            {renderListingType}
            {renderStatus}
            {renderVerification}
            {/* value coming from 'user-edit-view.tsx' to decide whether to show host dropdown select */}
            {showHostDropDown && renderHostFilter}
          </Stack>
        </Scrollbar>
      </Drawer>
    </>
  );
}
