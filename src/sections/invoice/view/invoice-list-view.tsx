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
import {
  useTable,
  TableNoData,
  TableHeadCustom,
  TableSelectedAction,
  TablePaginationCustom,
} from 'src/components/table';
import { getBookings } from 'src/utils/queries/bookings';
// types
import { IInvoiceTableFilterValue, IInvoiceTableFilters } from 'src/types/invoice';
import { Stack } from '@mui/system';
import { Divider } from '@mui/material';
import { LoadingButton } from '@mui/lab';
import { createPayment } from 'src/utils/queries/invoice';
import { format } from 'date-fns';
import { useRouter } from 'src/routes/hook';
import InvoiceTableToolbar from '../invoice-table-toolbar';
import InvoiceTableRow from '../invoice-table-row';
import InvoiceTableFiltersResult from '../invoice-table-filters-result';
import InvoiceAnalytic from '../invoice-analytic';
// ----------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: 'total', label: 'All' },
  { value: 'paid', label: 'Paid' },
  { value: 'unpaid', label: 'Pending' },
  { value: 'overdue', label: 'Overdue' },
];

const TABLE_HEAD = [
  { id: 'host', label: 'Host', width: 180 },
  { id: 'check_in', label: 'Check-in', width: 100 },
  { id: 'check_out', label: 'Checkout', width: 100 },
  { id: 'booked_on', label: 'Booked', width: 100 },
  { id: 'status', label: 'Status', width: 100 },
  { id: 'listing', label: 'Listing', width: 250 },
  { id: 'confirmation_code', label: 'Confirmation Code', width: 100 },
  { id: 'paid_amount', label: 'Total Payout', width: 100 },
];

const defaultFilters: IInvoiceTableFilters = {
  search: '',
  status: 'total',
  created_at_after: null,
  created_at_before: null,
  host: null,
};

// ----------------------------------------------------------------------

export default function BookingListView() {
  const table = useTable({
    defaultCurrentPage: 0,
    defaultRowsPerPage: 10,
  });
  const settings = useSettingsContext();
  const confirm = useBoolean();
  const loading = useBoolean();

  const downloadConfirm = useBoolean();
  const emptyData = useBoolean();

  const [tableData, setTableData] = useState<any>([]);
  const [tableMeta, setTableMeta] = useState<any>({ total: 0 });
  const [filters, setFilters] = useState(defaultFilters);

  const router = useRouter();

  const dataFiltered = tableData;
  const canReset = !isEqual(defaultFilters, filters);

  const notFound = (!dataFiltered.length && canReset) || !dataFiltered.length;

  const getBookingList = useCallback(async () => {
    try {
      const res = await getBookings({
        created_at_after: filters.created_at_after
          ? format(filters.created_at_after, 'yyyy-MM-dd')
          : null,
        created_at_before: filters.created_at_before
          ? format(filters.created_at_before, 'yyyy-MM-dd')
          : null,
        page_size: table.rowsPerPage,
        page: table.page + 1,
        search: filters.search,
        host: filters.host?.value,
        transactions: true,
        ...(filters.status === 'overdue' ? { over_due: true } : {}),
        host_payment_status:
          filters.status === 'total' || filters.status === 'overdue' ? null : filters.status,
      });
      if(!res.success) throw res.data;
      setTableData(res.data);

      const result: Record<string, any> = {};

      const totalStatusCount = res.host_payment_status_count
        ?.filter((item: any) => item.host_payment_status !== 'overdue')
        ?.reduce((total: number, item: any) => total + item.status_count, 0);
      const totalPayOut = res.host_payment_status_sum
        ?.filter((item: any) => item.host_payment_status !== 'overdue')
        ?.reduce((total: number, item: any) => total + item.total_pay_out, 0);

      res.host_payment_status_count?.forEach((statusCountItem: any) => {
        const matchingTotalPayOutItem = res.host_payment_status_sum?.find(
          (payOutItem: any) =>
            payOutItem.host_payment_status === statusCountItem.host_payment_status
        );

        if(matchingTotalPayOutItem) {
          const { host_payment_status, status_count } = statusCountItem;
          const { total_pay_out } = matchingTotalPayOutItem;
          const percentage = (total_pay_out / totalPayOut) * 100;

          result[host_payment_status] = {
            status_count,
            total_pay_out,
            percentage,
          };
        }
      });

      result.total = {
        status_count: totalStatusCount,
        total_pay_out: totalPayOut,
        percentage: 100,
      };

      setTableMeta({
        ...res.meta_data,
        stats: result,
      });
    } catch(err) {
      console.log(err);
    }
  }, [filters, table.page, table.rowsPerPage]);

  const handleCreateInvoice = useCallback(async () => {
    try {
      loading.onTrue();
      const res = await createPayment({
        booking_ids: table.selected.map((row: any) => row.id),
      });
      if(!res.success) throw res.data;
      confirm.onFalse();
      table.setSelected([]);
      router.push(`/transactions/${res.data.host_payment_id}`);
    } catch(err) {
      console.log(err);
    } finally {
      loading.onFalse();
    }
  }, [loading, table, router, confirm]);

  const handleFilters = useCallback(
    (name: string, value: IInvoiceTableFilterValue) => {
      table.onResetPage();
      setFilters((prevState) => ({
        ...prevState,
        [name]: value,
      }));
    },
    [table]
  );

  const handleFilterStatus = useCallback(
    (event: React.SyntheticEvent, newValue: string) => {
      handleFilters('status', newValue);
    },
    [handleFilters]
  );

  const handleResetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  useEffect(() => {
    getBookingList();
  }, [filters, getBookingList]);

  // Excel export function
  const handleExport = async () => {
    try {
      // const res = await getBookings({ transactions: true, page: 1, page_size: 100000000 });
      // if(!res.success) throw res.data;

      const res = await getBookings({
        created_at_after: filters.created_at_after
          ? format(filters.created_at_after, 'yyyy-MM-dd')
          : null,
        created_at_before: filters.created_at_before
          ? format(filters.created_at_before, 'yyyy-MM-dd')
          : null,
        page_size: 100000000,
        page: 1,
        search: filters.search,
        host: filters.host?.value,
        transactions: true,
        ...(filters.status === 'overdue' ? { over_due: true } : {}),
        host_payment_status:
          filters.status === 'total' || filters.status === 'overdue' ? null : filters.status,
      });
      if(!res.success) throw res.data;
      if(!res.data.length) {
        emptyData.onTrue()
        return;
      }

      const reportData = res.data;
      const dataForExport = reportData?.map((entry: any) => ({
        Host: entry?.host?.full_name,
        'Host Number': entry?.host?.phone_number,
        'Check-In': entry?.check_in,
        'Check-Out': entry?.check_out,
        Booked: entry?.created_at,
        Status: entry?.guest_payment_status,
        Listing: entry?.listing?.title,
      }));

      const worksheet = XLSX.utils.json_to_sheet(dataForExport);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Invoice List Report');
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `invoice_list_report_${today}.xlsx`);
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
              { name: 'Dashboard', href: paths.dashboard.root },
              { name: 'Transaction List' },
            ]}
            sx={{
              mb: { xs: 3, md: 5 },
            }}
          />
          <Button variant="contained" onClick={downloadConfirm.onTrue}>
            <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
          </Button>
        </Stack>
        <Card
          sx={{
            mb: { xs: 3, md: 5 },
          }}
        >
          <Scrollbar>
            <Stack
              direction="row"
              divider={<Divider orientation="vertical" flexItem sx={{ borderStyle: 'dashed' }} />}
              sx={{ py: 2 }}
            >
              <InvoiceAnalytic
                title="Total"
                total={tableMeta?.stats?.total?.status_count}
                percent={tableMeta?.stats?.total?.percentage}
                price={tableMeta?.stats?.total?.total_pay_out}
                icon="solar:bill-list-bold-duotone"
              // color={theme.palette.info.main}
              />

              <InvoiceAnalytic
                title="Paid"
                total={tableMeta?.stats?.paid?.status_count}
                percent={tableMeta?.stats?.paid?.percentage}
                price={tableMeta?.stats?.paid?.total_pay_out}
                icon="solar:file-check-bold-duotone"
              // color={theme.palette.success.main}
              />

              <InvoiceAnalytic
                title="Pending"
                total={tableMeta?.stats?.unpaid?.status_count}
                percent={tableMeta?.stats?.unpaid?.percentage}
                price={tableMeta?.stats?.unpaid?.total_pay_out}
                icon="solar:sort-by-time-bold-duotone"
              // color={theme.palette.warning.main}
              />

              <InvoiceAnalytic
                title="Overdue"
                total={tableMeta?.stats?.overdue?.status_count}
                percent={tableMeta?.stats?.overdue?.percentage}
                price={tableMeta?.stats?.overdue?.total_pay_out}
                icon="solar:bell-bing-bold-duotone"
              // color={theme.palette.error.main}
              />
            </Stack>
          </Scrollbar>
        </Card>
        <Card>
          <Tabs
            value={filters.status}
            onChange={handleFilterStatus}
            sx={{
              px: 2.5,
              boxShadow: (theme) => `inset 0 -2px 0 0 ${alpha(theme.palette.grey[500], 0.08)}`,
            }}
          >
            {STATUS_OPTIONS.map((tab) => (
              <Tab
                key={tab.value}
                iconPosition="end"
                value={tab.value}
                label={tab.label}
                icon={
                  <Label
                    variant={
                      ((tab.value === 'total' || tab.value === filters.status) && 'filled') ||
                      'soft'
                    }
                    color={
                      (tab.value === 'paid' && 'success') ||
                      (tab.value === 'unpaid' && 'warning') ||
                      (tab.value === 'overdue' && 'error') ||
                      'default'
                    }
                  >
                    {tableMeta?.stats?.[tab.value]?.status_count}
                  </Label>
                }
              />
            ))}
          </Tabs>

          <InvoiceTableToolbar filters={filters} onFilters={handleFilters} />

          {canReset && (
            <InvoiceTableFiltersResult
              filters={filters}
              onFilters={handleFilters}
              onResetFilters={handleResetFilters}
              results={tableMeta.total}
              sx={{ p: 2.5, pt: 0 }}
            />
          )}

          <TableContainer sx={{ position: 'relative', overflow: 'unset' }}>
            <TableSelectedAction
              dense={table.dense}
              numSelected={table.selected.length}
              rowCount={tableData?.length}
              onSelectAllRows={(checked) =>
                table.onSelectAllRows(
                  checked,
                  tableData?.map((row: any) => row)
                )
              }
              action={
                <Tooltip title="Delete">
                  <Button
                    variant="contained"
                    onClick={confirm.onTrue}
                    disabled={new Set(table.selected.map((row: any) => row.host.id)).size > 1}
                    startIcon={<Iconify icon="mingcute:add-line" />}
                  >
                    New Invoice
                  </Button>
                </Tooltip>
              }
            />

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
                      tableData.map((row: any) => row)
                    )
                  }
                />

                <TableBody>
                  {tableData.map((row: any) => (
                    <InvoiceTableRow
                      key={row.id}
                      row={row}
                      selected={table.selected.map((data: any) => data.id).includes(row.id)}
                      onSelectRow={() => table.onSelectRow(row)}
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
        open={confirm.value}
        onClose={confirm.onFalse}
        title="Create Invoice"
        content={
          <>
            Are you sure want to create invoice with <strong> {table.selected.length} </strong>{' '}
            items?
          </>
        }
        action={
          <LoadingButton
            loading={loading.value}
            variant="contained"
            color="primary"
            onClick={handleCreateInvoice}
          >
            Create
          </LoadingButton>
        }
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

    </>
  );
}
