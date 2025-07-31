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
// types
import { IUserTableFilterValue } from 'src/types/user';
// import { downloadCSV } from 'src/utils/queries/bookings';
import { Stack } from '@mui/material';
import ReferralTableRow from '../referral-table-row';
import ReferralTableFiltersResult from '../referral-table-filters-result';
import ReferralTableToolbar from '../referral-table-toolbar';
import { getReferrals } from '../../../utils/queries/referral';
import { IReferalTableFilters } from '../../../types/referral';

//

// ----------------------------------------------------------------------

const TABLE_HEAD = [
  { id: 'full_name ', label: 'Full Name' },
  { id: 'u_type', label: 'Role' },
  // { id: 'total_host_referrals_made', label: 'Host Referrals Made', width: 150 },
  { id: 'total_host_referrals_successful', label: 'Successful Host Referrals', width: 150 },
  { id: 'total_host_referral_earnings', label: 'Host Referral Earnings', width: 150 },
  // { id: 'total_guest_referrals_made', label: 'Guest Referrals Made', width: 150 },
  { id: 'total_guest_referrals_successful', label: 'Successful Guest Referrals', width: 150 },
  { id: 'total_guest_referral_points', label: 'Guest Referral Points', width: 150 },
  // { id: '', label: 'Action', width: 88 },
];

const defaultFilters: any = {
  username: '',
  email: '',
  referral_type: '',
  u_type: '',
};

// ----------------------------------------------------------------------

export default function ReferralListView() {
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
      setFilters((prevState: any) => ({
        ...prevState,
        [name]: value,
      }));
    },
    [table]
  );

  const handleResetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  const getReferralList = useCallback(async (data: any) => {
    try {
      const res = await getReferrals(data);
      if(!res.success) throw res.data;
      setTableData(res.data);
      // setTableMeta({ ...res.meta_data, user_status_count: res.user_status_count });
    } catch(err) {
      console.log(err);
    }
  }, []);

  useEffect(() => {
    getReferralList({
      ...filters,
      username: filters.username ? filters.username : null,
      email: filters.email ? filters.email : null,
      referral_type: filters.referral_type ? filters.referral_type : null,
      u_type: filters.u_type ? filters.u_type : null,
      page_size: table.rowsPerPage,
      page: table.page + 1,
    });
  }, [filters, getReferralList, table.page, table.rowsPerPage]);

  const handleExport = async () => {
    try {
      // const res = await getReferrals({ page: 1, page_size: 100000000 });
      const res = await getReferrals({
        username: filters.username ? filters.username : null,
        email: filters.email ? filters.email : null,
        referral_type: filters.referral_type ? filters.referral_type : null,
        u_type: filters.u_type ? filters.u_type : null,
        page_size: 100000000,
        page: 1,
      });
      if(!res.success) throw res.data;
      if(!res.data.length) {
        emptyData.onTrue()
        return;
      }
      if(!res.success) throw res.data;
      const reportData = res.data;
      const dataForExport = reportData?.map((entry: any) => ({
        'Full Name': entry?.full_name,
        Email: entry?.email,
        Role: entry?.u_type,
        // 'Host Referrals Made': entry?.total_host_referrals_made,
        'Successfu Host Referrals': entry?.total_host_referrals_successful,
        'Host Referral Earnings': entry?.total_host_referral_earnings,
        // 'Guest Referrals Made': entry?.total_guest_referrals_made,
        'Successfu Guest Referrals': entry?.total_guest_referrals_successful,
        'Guest Referrals Points': entry?.total_guest_referral_points,
      }));

      const worksheet = XLSX.utils.json_to_sheet(dataForExport);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Referral List Report');
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `referral_list_report_${today}.xlsx`);
    } catch(err) {
      console.log(err);
    }
  };

  return (
    <>
      <Container maxWidth={settings.themeStretch ? false : 'lg'}>
        <Stack
          spacing={3}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-end', sm: 'center' }}
          direction={{ xs: 'column', sm: 'row' }}
        >
          <CustomBreadcrumbs
            heading="List"
            links={[
              { name: 'Dashboard', href: paths.dashboard.referral.root },
              { name: 'Referral List' },
            ]}
            sx={{
              mb: { xs: 3, md: 5 },
            }}
          />
          <Button variant="contained" onClick={downloadConfirm.onTrue}>
            <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
          </Button>
        </Stack>

        <Card>
          <ReferralTableToolbar filters={filters} onFilters={handleFilters} />

          {canReset && (
            <ReferralTableFiltersResult
              filters={filters}
              onFilters={handleFilters}
              onResetFilters={handleResetFilters}
              results={tableMeta.total}
              sx={{ p: 2.5, pt: 0 }}
            />
          )}

          <TableContainer sx={{ position: 'relative', overflow: 'unset' }}>
            {/* <TableSelectedAction
              dense={table.dense}
              numSelected={table.selected.length}
              rowCount={tableData?.length}
              onSelectAllRows={(checked) =>
                table.onSelectAllRows(
                  checked,
                  tableData?.map((row: any) => row.id)
                )
              }
              action={
                <Tooltip title="Delete">
                  <IconButton color="primary" onClick={confirm.onTrue}>
                    <Iconify icon="solar:trash-bin-trash-bold" />
                  </IconButton>
                </Tooltip>
              }
            /> */}

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
                    <ReferralTableRow
                      key={row.id}
                      row={row}
                      selected={table.selected.includes(row.id)}
                      onSelectRow={() => table.onSelectRow(row.id)}
                      onDeleteRow={() => { }}
                      onEditRow={() => { }}
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
