// @mui
import { useCallback, useEffect, useState } from 'react';
import { useTheme } from '@mui/material/styles';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Unstable_Grid2';

import { useMockedUser } from 'src/hooks/use-mocked-user';
import { _appFeatured, _appAuthors, _appInstalled, _appRelated, _appInvoices } from 'src/_mock';
import { useSettingsContext } from 'src/components/settings';
import { getBestSellingHosts, getDashboardStat, getStatistics } from 'src/utils/queries/dashboard';
import { DashboardStat } from 'src/types/dashboard';

import {
  Box,
  Card,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  OutlinedInput,
  Radio,
  Select,
  TableBody,
  TableContainer,
  Typography,
} from '@mui/material';
import { TableHeadCustom, TableNoData } from 'src/components/table';
import Scrollbar from 'src/components/scrollbar';
import Table from '@mui/material/Table';
import { getBookings, getLatestBookings } from 'src/utils/queries/bookings';
import { startCase } from 'lodash';
import { RightIcon } from 'src/components/carousel/arrow-icons';

import BookingTableRow from '../booking-table-row';
import AnalyticsWidgetSummary from '../../analytics/analytics-widget-summary';
import BookingStatistics from '../booking-statistics';
import AppFeatured from '../app-featured';
import HostTableRow from '../host-table-row';
//

const filterOptions = [
  // { label: 'Weekly', value: 'WEEKLY' },
  // { label: 'Monthly', value: 'MONTHLY' },
  // { label: 'Yearly', value: 'YEARLY' },
  { label: 'WEEKLY', value: 'WEEKLY' },
  { label: 'MONTHLY', value: 'MONTHLY' },
  { label: 'YEARLY', value: 'YEARLY' },
];

const sortFieldFilterOptions = [
  { label: 'Total Sell Amount', value: 'total_sell_amount' },
  { label: 'Total Property', value: 'total_property' },
  { label: 'First Name', value: 'first_name' },
  { label: 'Last Name', value: 'last_name' },
];

const sortOrderFilterOptions = [
  { label: 'Low to High', value: 'asc' },
  { label: 'High to Low', value: 'desc' },
];

// ----------------------------------------------------------------------

const TABLE_HEAD = [
  { id: 'listing', label: 'Listing', width: 180 },
  { id: 'guest', label: 'Guest', width: 180 },
  { id: 'host', label: 'Host', width: 180 },
  { id: 'check_in', label: 'Check-in', width: 100 },
  { id: 'check_out', label: 'Checkout', width: 100 },
  { id: 'booked', label: 'Booked', width: 100 },
  { id: 'status', label: 'Status', width: 100 },
];

const HOST_TABLE_HEAD = [
  { id: 'host', label: 'Host', width: 180 },
  { id: 'property', label: 'Property', width: 180 },
  { id: 'total', label: 'Total Amount', width: 100 },
];

export default function OverviewAppView() {
  const { user } = useMockedUser();
  const [stats, setStats] = useState<DashboardStat>();
  const [filters, setFilters] = useState({
    bookingStatYear: 2024,
    topSellingFilter: 'MONTHLY',
    countStatFilter: 'MONTHLY',
    sortField: 'total_sell_amount',
    sortOrder: 'desc',
  });

  const settings = useSettingsContext();

  const fetchDashboardStat = useCallback(async () => {
    try {
      const dashboardStat = await getDashboardStat({ query_type: filters.countStatFilter });
      if (!dashboardStat.success) throw dashboardStat.data;
      setStats((prevStats: any) => ({ ...prevStats, count_stat: dashboardStat?.data }));
    } catch (err) {
      console.error(err);
    }
  }, [filters.countStatFilter]);

  const fetchStatistics = useCallback(async () => {
    try {
      const stat = await getStatistics({ year: filters.bookingStatYear });
      if (!stat.success) throw stat.data;
      setStats((prevStats: any) => ({ ...prevStats, booking_stat: stat?.data }));
    } catch (err) {
      console.error(err);
    }
  }, [filters.bookingStatYear]);

  const fetchBookings = useCallback(async () => {
    try {
      const bookingList = await getLatestBookings({ page_size: 5 });
      if (!bookingList.success) throw bookingList.data;
      setStats((prevStats) => ({ ...prevStats, bookings: bookingList?.data }));
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchBestSellingHosts = useCallback(async () => {
    try {
      const hostList = await getBestSellingHosts({
        page_size: 5,
        query_type: filters.topSellingFilter,
        sort_by: filters.sortField,
        order: filters.sortOrder
      });
      if (!hostList.success) throw hostList.data;
      setStats((prevStats: any) => ({ ...prevStats, best_selling_hosts: hostList.data }));
    } catch (err) {
      console.error(err);
    }
  }, [filters.topSellingFilter, filters.sortField, filters.sortOrder]);

  useEffect(() => {
    fetchDashboardStat();
  }, [fetchDashboardStat]);

  useEffect(() => {
    fetchStatistics();
  }, [fetchStatistics]);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  useEffect(() => {
    fetchBestSellingHosts();
  }, [fetchBestSellingHosts]);

  return (
    <Container maxWidth={settings.themeStretch ? false : 'xl'}>
      <Grid container spacing={3}>
        <Grid xs={12}>
          <Box sx={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between'}}>
            <Typography variant="h5" sx={{ ml: 2, mb: 2, mt: 2 }}>
              Best Selling Host
            </Typography>
            <FormControl
              sx={{
                flexShrink: 1,
                width: { xs: '200px' },
              }}
            >
              <Select
                value={filters?.countStatFilter}
                onChange={(val) =>
                  setFilters?.((prev: any) => ({
                    ...(prev || {}),
                    countStatFilter: val.target.value,
                  }))
                }
                renderValue={(selected) => startCase(selected?.toLowerCase())}
                MenuProps={{
                  PaperProps: {
                    sx: { maxHeight: 240 },
                  },
                }}
              >
                {filterOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    <Radio
                      disableRipple
                      size="small"
                      checked={filters?.countStatFilter === option.value}
                    />
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </Grid>

        <Grid xs={12} sm={6} md={3}>
          <AnalyticsWidgetSummary
            title="Bookings"
            total={stats?.count_stat?.success_booking_count || 0}
            icon={<img alt="icon" src="/assets/icons/glass/ic_glass_bag.png" />}
          />
        </Grid>

        <Grid xs={12} sm={6} md={3}>
          <AnalyticsWidgetSummary
            title="Profit"
            total={parseFloat((stats?.count_stat?.total_profit ?? 0).toFixed(2))}
            unit="৳"
            color="info"
            icon={<img alt="icon" src="/assets/icons/glass/ic_glass_users.png" />}
          />
        </Grid>

        <Grid xs={12} sm={6} md={3}>
          <AnalyticsWidgetSummary
            title="New Users"
            total={stats?.count_stat?.user_count || 0}
            color="warning"
            icon={<img alt="icon" src="/assets/icons/glass/ic_glass_buy.png" />}
          />
        </Grid>

        <Grid xs={12} sm={6} md={3}>
          <AnalyticsWidgetSummary
            title="Booking Cancelled"
            total={stats?.count_stat?.cancelled_booking_count || 0}
            color="error"
            icon={<img alt="icon" src="/assets/icons/glass/ic_glass_message.png" />}
          />
        </Grid>
        <Grid xs={12} md={12}>
          <Box>
            <BookingStatistics
              title="Statistics"
              setFilters={setFilters}
              filters={filters}
              subheader={`You are seeing the statistic of year-${filters.bookingStatYear}`}
              chart={{
                categories: [
                  'Jan',
                  'Feb',
                  'Mar',
                  'Apr',
                  'May',
                  'Jun',
                  'Jul',
                  'Aug',
                  'Sep',
                  'Oct',
                  'Nov',
                  'Dec',
                ],
                series: [
                  {
                    name: 'Booked',
                    data: Object.keys(stats?.booking_stat || {}).map(
                      (item) => stats?.booking_stat?.[item]?.confirmed || 0
                    ),
                  },
                  {
                    name: 'Cancelled',
                    data: Object.keys(stats?.booking_stat || {}).map(
                      (item) => stats?.booking_stat?.[item]?.cancelled || 0
                    ),
                  },
                ],
              }}
            />
          </Box>
        </Grid>

        <TableContainer sx={{ position: 'relative', overflow: 'unset', marginTop: 2 }}>
          <Card sx={{ margin: 2, padding: 2 }}>
            <Box sx={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between' }}>
              <Typography variant="h5" sx={{ ml: 2, mb: 2, mt: 2 }}>
                Best Selling Host
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', gap: 1 }}>
                <FormControl
                  sx={{
                    flexShrink: 1,
                    width: { xs: '200px' },
                  }}
                >
                  <Select
                    value={filters?.topSellingFilter}
                    onChange={(val) =>
                      setFilters?.((prev: any) => ({
                        ...(prev || {}),
                        topSellingFilter: val.target.value,
                      }))
                    }
                    renderValue={(selected) => startCase(selected?.toLowerCase())}
                    MenuProps={{
                      PaperProps: {
                        sx: { maxHeight: 240 },
                      },
                    }}
                  >
                    {filterOptions.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        <Radio
                          disableRipple
                          size="small"
                          checked={filters?.topSellingFilter === option.value}
                        />
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl
                  sx={{
                    flexShrink: 1,
                    width: { xs: '200px' },
                  }}
                >
                  <Select
                    value={filters?.sortField}
                    onChange={(val) =>
                      setFilters?.((prev: any) => ({
                        ...(prev || {}),
                        sortField: val.target.value,
                      }))
                    }
                    renderValue={(selected) => startCase(selected?.toLowerCase())}
                    MenuProps={{
                      PaperProps: {
                        sx: { maxHeight: 240 },
                      },
                    }}
                  >
                    {sortFieldFilterOptions.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        <Radio
                          disableRipple
                          size="small"
                          checked={filters?.sortField === option.value}
                        />
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl
                  sx={{
                    flexShrink: 1,
                    width: { xs: '200px' },
                  }}
                >
                  <Select
                    value={filters?.sortOrder}
                    onChange={(val) =>
                      setFilters?.((prev: any) => ({
                        ...(prev || {}),
                        sortOrder: val.target.value,
                      }))
                    }
                    renderValue={(selected) => startCase(selected?.toLowerCase())}
                    MenuProps={{
                      PaperProps: {
                        sx: { maxHeight: 240 },
                      },
                    }}
                  >
                    {sortOrderFilterOptions.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        <Radio
                          disableRipple
                          size="small"
                          checked={filters?.sortOrder === option.value}
                        />
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            </Box>
            <Scrollbar>
              <Table size="small" sx={{ minWidth: 960 }}>
                <TableHeadCustom
                  headLabel={HOST_TABLE_HEAD}
                  rowCount={stats?.best_selling_hosts?.length}
                />

                <TableBody>
                  {stats?.best_selling_hosts?.map((row: any) => (
                    <HostTableRow key={row.id} row={row} />
                  ))}
                </TableBody>
              </Table>
            </Scrollbar>
          </Card>
        </TableContainer>
        <TableContainer sx={{ position: 'relative', overflow: 'unset' }}>
          <Card sx={{ margin: 2, padding: 2 }}>
            <Box sx={{ display: 'flex' }}>
              <Typography variant="h5" sx={{ ml: 2, mb: 2, mt: 2 }}>
                Latest Bookings
              </Typography>
            </Box>
            <Scrollbar>
              <Table size="small" sx={{ minWidth: 960 }}>
                <TableHeadCustom headLabel={TABLE_HEAD} rowCount={stats?.bookings?.length} />

                <TableBody>
                  {stats?.bookings?.map((row: any) => (
                    <BookingTableRow key={row.id} row={row} />
                  ))}
                </TableBody>
              </Table>
            </Scrollbar>
            <Box sx={{ marginTop: 1, textAlign: 'right', marginRight: 3 }}>
              <Link
                href="/booking/list"
                sx={{ display: 'flex', justifyContent: 'end', alignItems: 'center' }}
              >
                View All <RightIcon />
              </Link>
            </Box>
          </Card>
        </TableContainer>
      </Grid>
    </Container>
  );
}
