import isEqual from 'lodash/isEqual';
import { useCallback, useEffect, useState } from 'react';
import * as XLSX from 'xlsx';
// @mui
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Container from '@mui/material/Container';
import IconButton from '@mui/material/IconButton';
import { alpha } from '@mui/material/styles';
import Tab from '@mui/material/Tab';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableContainer from '@mui/material/TableContainer';
import Tabs from '@mui/material/Tabs';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
// routes
import { paths } from 'src/routes/paths';
// hooks
import { useBoolean } from 'src/hooks/use-boolean';
// components
import { format } from 'date-fns';
import CustomBreadcrumbs from 'src/components/custom-breadcrumbs';
import { ConfirmDialog } from 'src/components/custom-dialog';
import Iconify from 'src/components/iconify';
import Label from 'src/components/label';
import Scrollbar from 'src/components/scrollbar';
import { useSettingsContext } from 'src/components/settings';
import {
  TableHeadCustom,
  TableNoData,
  TablePaginationCustom,
  TableSelectedAction,
  useTable,
} from 'src/components/table';
// types
import { IPayoutTableFilters, IPayoutTableFilterValue } from 'src/types/payout';
import { getPayments } from 'src/utils/queries/invoice';
import PayoutTableFilterResults from '../payout-table-filters-result';
import PayoutTableRow from '../payout-table-row';
import PayoutTableFilters from '../payout-table-toolbar';


// ----------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'paid', label: 'Paid' },
  { value: 'unpaid', label: 'Unpaid' },
];

const TABLE_HEAD = [
  { id: 'invoice_no', label: 'Invoice Number' },
  { id: 'payment_date', label: 'Payment Date', width: 180 },
  { id: 'host', label: 'Payment To', width: 220 },
  { id: 'pay_method', label: 'Payment Method', width: 180 },
  { id: 'total_amount', label: 'Total Amount', width: 100 },
  { id: 'status', label: 'Status', width: 100 },
];

const defaultFilters: IPayoutTableFilters = {
  search: '',
  host: null,
  status: 'all',
  payment_date_before: null,
  payment_date_after: null,
};
interface IPayoutListViewProps {
  fromUserDetails?: boolean;
  userId?: number;
}

// ----------------------------------------------------------------------

export default function PayoutListView({ fromUserDetails = false, userId }: IPayoutListViewProps) {
  const table = useTable({
    defaultCurrentPage: 0,
    defaultRowsPerPage: 10,
  });
  const settings = useSettingsContext();
  const confirm = useBoolean();
  const downloadConfirm = useBoolean();
  const emptyData = useBoolean();

  const [tableData, setTableData] = useState<any>([]);
  const [tableMeta, setTableMeta] = useState<any>({ total: 0 });
  const [filters, setFilters] = useState(defaultFilters);

  const dataFiltered = tableData;
  const canReset = !isEqual(defaultFilters, filters);

  const notFound = (!dataFiltered.length && canReset) || !dataFiltered.length;

  const handleFilters = useCallback(
    (name: string, value: IPayoutTableFilterValue) => {
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

  const getPaymentList = useCallback(async (data: any) => {
    try {
      const res = await getPayments(data);
      if(!res.success) throw res.data;
      setTableData(res.data);
      setTableMeta({ ...res.meta_data, status_count: res.status_count });
    } catch(err) {
      console.log(err);
    }
  }, []);

  useEffect(() => {
    getPaymentList({
      ...filters,
      payment_date_after: filters.payment_date_after
        ? format(filters.payment_date_after, 'yyyy-MM-dd')
        : null,
      payment_date_before: filters.payment_date_before
        ? format(filters.payment_date_before, 'yyyy-MM-dd')
        : null,
      host: fromUserDetails ? userId : filters.host?.value,
      page_size: table.rowsPerPage,
      page: table.page + 1,
      status: filters.status === 'all' ? null : filters.status,
    });
  }, [filters, fromUserDetails, getPaymentList, table.page, table.rowsPerPage, userId]);

  // Excel export function
  const handleExport = async () => {
    try {
      // const res = await getPayments({ page: 1, page_size: 100000000 });
      // if (!res.success) throw res.data;

      const res = await getPayments({
        payment_date_after: filters.payment_date_after
          ? format(filters.payment_date_after, 'yyyy-MM-dd')
          : null,
        payment_date_before: filters.payment_date_before
          ? format(filters.payment_date_before, 'yyyy-MM-dd')
          : null,
        host: fromUserDetails ? userId : filters.host?.value,
        page_size: 100000000,
        page: 1,
        status: filters.status === 'all' ? null : filters.status,
      });
      if(!res.success) throw res.data;
      if(!res.data.length) {
        emptyData.onTrue()
        return;
      }

      const reportData = res.data;
      const dataForExport = reportData?.map((entry: any) => ({
        'Invoice Number': entry?.invoice_no,
        'Payment Date': entry?.payment_date,
        'Payment To': entry?.host?.full_name,
        'Payment Method': entry?.pay_method?.m_type,
        'Account No.': entry?.pay_method?.account_no,
        'Total Amount': entry?.total_amount,
        Status: entry?.status,
      }));

      const worksheet = XLSX.utils.json_to_sheet(dataForExport);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Payout List Report');
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(workbook, `payout_list_report_${today}.xlsx`);
    } catch(err) {
      console.log(err);
    }
  };

  return (
    <>
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
              links={[{ name: 'Dashboard', href: paths.dashboard.root }, { name: 'Payout List' }]}
              sx={{
                mb: { xs: 3, md: 5 },
              }}
            />
            <Button variant="contained" onClick={downloadConfirm.onTrue}>
              <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
            </Button>
          </Stack>
        )}

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
                      ((tab.value === 'all' || tab.value === filters.status) && 'filled') || 'soft'
                    }
                    color={
                      (tab.value === 'paid' && 'success') ||
                      (tab.value === 'unpaid' && 'warning') ||
                      'default'
                    }
                  >
                    {tab.value === 'all'
                      ? tableMeta.status_count?.reduce(
                        (acc: number, cur: any) => acc + cur.status_count,
                        0
                      )
                      : tableMeta?.status_count?.find((count: any) => count.status === tab.value)
                        ?.status_count || 0}
                  </Label>
                }
              />
            ))}
          </Tabs>

          <PayoutTableFilters
            filters={filters}
            onFilters={handleFilters}
            showHostFilter={!fromUserDetails}
          />

          {canReset && (
            <PayoutTableFilterResults
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
                      tableData.map((row: any) => row.id)
                    )
                  }
                />

                <TableBody>
                  {tableData.map((row: any) => (
                    <PayoutTableRow
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
        open={confirm.value}
        onClose={confirm.onFalse}
        title="Delete"
        content={
          <>
            Are you sure want to delete <strong> {table.selected.length} </strong> items?
          </>
        }
        action={
          <Button
            variant="contained"
            color="error"
            onClick={() => {
              confirm.onFalse();
            }}
          >
            Delete
          </Button>
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
