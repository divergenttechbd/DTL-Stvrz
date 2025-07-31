import { useCallback, useEffect, useState } from 'react';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import * as XLSX from 'xlsx';
import Iconify from 'src/components/iconify';
import Button from '@mui/material/Button';
// routes
import { paths } from 'src/routes/paths';
// hooks
import { useBoolean } from 'src/hooks/use-boolean';
// utils
// assets
import CustomBreadcrumbs from 'src/components/custom-breadcrumbs';
import EmptyContent from 'src/components/empty-content';
import { useSettingsContext } from 'src/components/settings';
import { ConfirmDialog } from 'src/components/custom-dialog';
// types
import { IListingFilters, IListingItem, ITourFilterValue } from 'src/types/listing';
//
import { format } from 'date-fns';
import { getListingCategories, getListings, getListingsLite } from 'src/utils/queries/listing';
import TourFilters from '../listing-filters';
import TourFiltersResult from '../listing-filters-result';
import TourList from '../listing-list';
import TourSearch, { IListingItemLite } from '../listing-search';
import TourSort from '../listing-sort';

// ----------------------------------------------------------------------
export const sortOptions = [
  { value: 'newest', label: 'Newest' },
  { value: 'popular', label: 'Popular' },
  { value: 'oldest', label: 'Oldest' },
];

const defaultFilters: IListingFilters = {
  created_at_after: null,
  created_at_before: null,
  status: '',
  verification_status: '',
  category: '',
  page_size: 12,
  page: 1,
  sort_by: 'latest',
  host: null,
  latitude: '',
  longitude: '',
  radius: 25,
  district: '',
  sub_disctrict: '',
};

// ----------------------------------------------------------------------

// these props will help to identify the exact user when this component will be called from the 'user-edit-view.tsx' (user detail)
type ListingsListViewProps = {
  fromUserDetails?: boolean;
  userId?: number;
};

export default function TourListView({ fromUserDetails, userId }: ListingsListViewProps) {
  // console.log('listings ---', fromUserDetails, userId)
  const settings = useSettingsContext();

  const openFilters = useBoolean();
  const downloadConfirm = useBoolean();
  const emptyData = useBoolean();

  const [listData, setListData] = useState<IListingItem[]>([]);
  // console.log('listData', listData);
  const [listMeta, setListMeta] = useState<any>();
  const [categoryOptions, setCategoryOptions] = useState<
    {
      label: string;
      value: string | number;
    }[]
  >([]);
  const [search, setSearch] = useState<{ query: string; results: IListingItemLite[] }>({
    query: '',
    results: [],
  });

  const [filters, setFilters] = useState(defaultFilters);

  const getListingList = useCallback(async (data: any) => {
    try {
      const res = await getListings(data);
      if(!res.success) throw res.data;
      setListData(res.data);
      setListMeta(res.meta_data);

      const categories = await getListingCategories();
      setCategoryOptions(categories.data.map((d: any) => ({ label: d.name, value: d.id })));
    } catch(err) {
      console.log(err);
    }
  }, []);

  useEffect(() => {
    getListingList({
      category: filters.category,
      verification_status: filters.verification_status,
      status: filters.status,
      created_at_before: filters.created_at_before
        ? format(filters.created_at_before, 'yyyy-MM-dd')
        : null,
      created_at_after: filters.created_at_after
        ? format(filters.created_at_after, 'yyyy-MM-dd')
        : null,
      page_size: filters.page_size,
      page: filters.page,
      sort_by: filters.sort_by,
      host: userId || filters.host?.value,
      latitude: filters.latitude,
      longitude: filters.longitude,
      radius: 25,
    });
  }, [filters, getListingList, userId]);

  const dateError =
    filters.created_at_after && filters.created_at_before
      ? filters.created_at_after.getTime() > filters.created_at_before.getTime()
      : false;

  const canReset =
    !!filters.category ||
    !!filters.status ||
    !!filters.verification_status ||
    !!filters.host ||
    (!!filters.created_at_after && !!filters.created_at_before);

  const notFound = !listData.length && canReset;

  const handleFilters = useCallback((name: string, value: ITourFilterValue) => {
    setFilters((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  }, []);

  const handleSortBy = useCallback(
    (newValue: string) => {
      handleFilters('sort_by', newValue);
    },
    [handleFilters]
  );

  const handleSearch = useCallback(async (inputValue: string) => {
    setSearch((prevState) => ({
      ...prevState,
      query: inputValue,
    }));

    if(inputValue) {
      const results = await getListingsLite({ search: inputValue });

      setSearch((prevState) => ({
        ...prevState,
        results: results.data || [],
      }));
    }
  }, []);

  const handleResetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  const handlePaginationChange = useCallback((event: React.ChangeEvent<unknown>, value: number) => {
    setFilters((prev) => ({ ...prev, page: value }));
  }, []);

  const renderFilters = (
    <Stack
      spacing={3}
      justifyContent="space-between"
      alignItems={{ xs: 'flex-end', sm: 'center' }}
      direction={{ xs: 'column', sm: 'row' }}
    >
      <TourSearch
        query={search.query}
        results={search.results}
        onSearch={handleSearch}
        hrefItem={(id: string) => paths.dashboard.listing.details(id)}
      />

      <Stack direction="row" spacing={1} flexShrink={0}>
        <TourFilters
          open={openFilters.value}
          onOpen={openFilters.onTrue}
          onClose={openFilters.onFalse}
          filters={filters}
          onFilters={handleFilters}
          categoryOptions={categoryOptions}
          canReset={canReset}
          onResetFilters={handleResetFilters}
          dateError={dateError}
          showHostDropDown={!fromUserDetails}
        />

        <TourSort sort={filters.sort_by} onSort={handleSortBy} sortOptions={sortOptions} />
      </Stack>
    </Stack>
  );

  const renderResults = (
    <TourFiltersResult
      filters={filters}
      onResetFilters={handleResetFilters}
      canReset={canReset}
      onFilters={handleFilters}
      results={listMeta?.total || 0}
    />
  );

  // Excel export function
  const handleExport = async () => {
    try {
      const res = await getListings({
        category: filters.category,
        verification_status: filters.verification_status,
        status: filters.status,
        created_at_before: filters.created_at_before
          ? format(filters.created_at_before, 'yyyy-MM-dd')
          : null,
        created_at_after: filters.created_at_after
          ? format(filters.created_at_after, 'yyyy-MM-dd')
          : null,
        page_size: 100000000,
        page: 1,
        sort_by: filters.sort_by,
        host: userId || filters.host?.value,
        latitude: filters.latitude,
        longitude: filters.longitude,
        radius: 25,
      });
      if(!res.success) throw res.data;
      if(!res.data.length) {
        emptyData.onTrue()
        return;
      }
      const dataForExport = res.data?.map((entry: any) => ({
        Title: entry?.title,
        Address: entry?.address,
        Price: entry?.price,
        Host: entry?.owner?.full_name,
        "Total Bookings": entry?.total_booking_count,
        Status: entry?.status,
        Rating: entry?.avg_rating,
      }));

      const worksheet = XLSX.utils.json_to_sheet(dataForExport);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Booking List Report');
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `booking_list_report_${today}.xlsx`);
    } catch(err) {
      console.log(err);
    }
  };

  return (
    <Container maxWidth={settings.themeStretch ? false : 'lg'}>
      {!fromUserDetails && (
        <Stack
          spacing={3}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-end', sm: 'center' }}
          direction={{ xs: 'column', sm: 'row' }}
        >
          <CustomBreadcrumbs
            heading="List"
            links={[
              { name: 'Dashboard', href: paths.dashboard.root },
              {
                name: 'Tour',
                href: paths.dashboard.listing.root,
              },
              { name: 'List' },
            ]}
            sx={{
              mb: { xs: 3, md: 5 },
            }}
          />
          <Button variant="contained" onClick={downloadConfirm.onTrue}>
            <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
          </Button>
        </Stack>
      )}

      <Stack
        spacing={2.5}
        sx={{
          mb: { xs: 3, md: 5 },
        }}
      >
        {renderFilters}

        {canReset && renderResults}
      </Stack>

      {notFound && <EmptyContent title="No Data" filled sx={{ py: 10 }} />}

      <TourList
        tours={listData}
        onPaginationChange={handlePaginationChange}
        totalPage={Math.ceil((listMeta?.total || 0) / filters.page_size)}
      />

      <ConfirmDialog
        open={downloadConfirm.value}
        onClose={downloadConfirm.onFalse}
        title="Download Report"
        content={<>Are you sure want to download report?</>}
        action={
          <Button
            variant="contained"
            color="success"
            onClick={() => {
              handleExport();
              downloadConfirm.onFalse();
            }}
          >
            Download
          </Button>
        }
      />

      <ConfirmDialog
        open={emptyData.value}
        onClose={emptyData.onFalse}
        title="No data found"
        content={<>Couldn&apos;t find any matching records.</>}
        action={null}
      />

    </Container>
  );
}
