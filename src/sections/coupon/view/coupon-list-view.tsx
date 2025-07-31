import isEqual from 'lodash/isEqual';
import { useState, useCallback, useEffect } from 'react';
import * as XLSX from 'xlsx';
// @mui
import { alpha } from '@mui/material/styles';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Card from '@mui/material/Card';
import Table from '@mui/material/Table';
import Button from '@mui/material/Button';
import Tooltip from '@mui/material/Tooltip';
import Container from '@mui/material/Container';
import TableBody from '@mui/material/TableBody';
import IconButton from '@mui/material/IconButton';
import TableContainer from '@mui/material/TableContainer';
// routes
import { paths } from 'src/routes/paths';
// hooks
import { useBoolean } from 'src/hooks/use-boolean';
// components
import Label from 'src/components/label';
import Iconify from 'src/components/iconify';
import Scrollbar from 'src/components/scrollbar';
import { ConfirmDialog } from 'src/components/custom-dialog';
import { useSettingsContext } from 'src/components/settings';
import CustomBreadcrumbs from 'src/components/custom-breadcrumbs';
import { format } from 'date-fns';
import {
  useTable,
  TableNoData,
  TableHeadCustom,
  TableSelectedAction,
  TablePaginationCustom,
} from 'src/components/table';
import { downloadUserCSV, getUsers, updateUser } from 'src/utils/queries/users';
// types
import { IUserTableFilters, IUserTableFilterValue } from 'src/types/user';
// import { downloadCSV } from 'src/utils/queries/bookings';
import { Box, Stack } from '@mui/material';

//
import CouponTableRow from '../coupon-table-row';
import UserTableToolbar from '../user-table-toolbar';
import UserTableFiltersResult from '../user-table-filters-result';
import { getCoupons } from '../../../utils/queries/coupon';

// ----------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'deactivated', label: 'Deactivated' },
  { value: 'restricted', label: 'Restricted' },
];

const TABLE_HEAD = [
  { id: 'code', label: 'Code' },
  { id: 'description', label: 'Description', width: 220 },
  { id: 'discount_type', label: 'Discount Type', width: 220 },
  { id: 'discount_value', label: 'Discount Value', width: 180 },
  { id: 'is_active', label: 'Status', width: 180 },
  { id: 'uses_count', label: 'Uses Count', width: 180 },
  { id: '', label: 'Validity', width: 180 },
  { id: '', label: 'Action', width: 88 },
];

const defaultFilters: IUserTableFilters = {
  search: '',
  u_type: '',
  status: 'all',
  identity_verification_status: '',
  date_joined_after: null,
  date_joined_before: null,
};

// ----------------------------------------------------------------------

export default function CouponListView() {
  const table = useTable({
    defaultCurrentPage: 0,
    defaultRowsPerPage: 10,
  });
  const settings = useSettingsContext();
  const downloadConfirm = useBoolean();
  const emptyData = useBoolean();

  const [tableData, setTableData] = useState<any>([]);
  const [tableMeta, setTableMeta] = useState<any>({ total: 0 });
  const [filters, setFilters] = useState(defaultFilters);

  const dataFiltered = tableData;
  const canReset = !isEqual(defaultFilters, filters);

  const notFound = (!dataFiltered.length && canReset) || !dataFiltered.length;

  const handleFilters = useCallback(
    (name: string, value: IUserTableFilterValue) => {
      table.onResetPage();
      setFilters((prevState) => ({
        ...prevState,
        [name]: value,
      }));
    },
    [table]
  );

  const handleResetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  const handleDownload = useCallback(async () => {
    try {
      await downloadUserCSV(
        table.selected.length
          ? {
            ids: table.selected,
          }
          : {
            date_joined_after: filters.date_joined_after
              ? format(filters.date_joined_after, 'yyyy-MM-dd')
              : null,
            date_joined_before: filters.date_joined_before
              ? format(filters.date_joined_before, 'yyyy-MM-dd')
              : null,
            u_type: filters.u_type,
            identity_verification_status: filters.identity_verification_status,
            search: filters.search,
            status: filters.status === 'all' ? null : filters.status,
            page_size: 0,
            report_download: true,
          }
      );
    } catch(e) {
      console.log(e);
    }
  }, [table, filters]);

  const getCouponList = useCallback(async (data: any) => {
    try {
      const res = await getCoupons(data);
      if(!res.success) throw res.data;
      console.log('coupon data--------------', res.data);
      setTableData(res.data);
      // setTableMeta({ ...res.meta_data, user_status_count: res.user_status_count });
    } catch(err) {
      console.log(err);
    }
  }, []);

  useEffect(() => {
    getCouponList({
      page_size: table.rowsPerPage,
      page: table.page + 1,
    });
  }, [table.page, table.rowsPerPage, getCouponList]);

  const handleExport = async () => {
    try {
      const res = await getCoupons({ page: 1, page_size: 100000000 });
      if(!res.success) throw res.data;
      if(!res.data.length) {
        emptyData.onTrue()
        return;
      }
      const reportData = res.data;
      const dataForExport = reportData?.map((entry: any) => ({
        Code: entry?.code,
        Description: entry?.description,
        'Discount Type': entry?.discount_type,
        'Discount Value': entry?.discount_value,
        Status: entry?.is_active ? 'Active' : 'Inactive',
        'Uses Code': entry?.uses_count,
        'Valid From': entry?.valid_from,
        'Valid To': entry?.valid_to,
      }));

      const worksheet = XLSX.utils.json_to_sheet(dataForExport);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Coupon List Report');
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `coupon_list_report_${today}.xlsx`);
    } catch(err) {
      console.log(err);
    }
  };

  return (
    <>
      <Container maxWidth={settings.themeStretch ? false : 'lg'}>
        <CustomBreadcrumbs
          heading="List"
          links={[{ name: 'Dashboard', href: paths.dashboard.root }, { name: 'Coupon List' }]}
          sx={{
            mb: { xs: 3, md: 5 },
          }}
          action={
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
              <Button
                // component={RouterLink}
                href={paths.dashboard.coupon.new}
                variant="contained"
                startIcon={<Iconify icon="mingcute:add-line" />}
              >
                New Coupon
              </Button>
              <Button variant="contained" onClick={downloadConfirm.onTrue}>
                <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
              </Button>
            </Box>
          }
        />
        <Card>
          <TableContainer sx={{ position: 'relative', overflow: 'unset' }}>
            <Scrollbar>
              <Table size={table.dense ? 'small' : 'medium'} sx={{ minWidth: 960 }}>
                <TableHeadCustom
                  order={table.order}
                  orderBy={table.orderBy}
                  headLabel={TABLE_HEAD}
                  rowCount={tableData.length}
                  numSelected={table.selected.length}
                  onSort={table.onSort}
                  onSelectAllRows={(checked) =>
                    table.onSelectAllRows(
                      checked,
                      tableData.map((row: any) => row.id)
                    )
                  }
                />

                <TableBody>
                  {tableData.map((row: any) => (
                    <CouponTableRow
                      key={row.id}
                      row={row}
                      selected={table.selected.includes(row.id)}
                      onSelectRow={() => table.onSelectRow(row.id)}
                      onDeleteRow={() => { }}
                    />
                  ))}

                  <TableNoData notFound={notFound} />
                </TableBody>
              </Table>
            </Scrollbar>
          </TableContainer>

          <TablePaginationCustom
            count={tableMeta.total}
            page={table.page}
            rowsPerPage={table.rowsPerPage}
            onPageChange={table.onChangePage}
            onRowsPerPageChange={table.onChangeRowsPerPage}
            dense={table.dense}
            onChangeDense={table.onChangeDense}
          />
        </Card>
      </Container>

      <ConfirmDialog
        open={downloadConfirm.value}
        onClose={downloadConfirm.onFalse}
        title="Download"
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

    </>
  );
}
