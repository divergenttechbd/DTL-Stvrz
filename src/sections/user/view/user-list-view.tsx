import isEqual from 'lodash/isEqual';
import { useState, useCallback, useEffect } from 'react';
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
import { Stack } from '@mui/material';

//
import UserTableRow from '../user-table-row';
import UserTableToolbar from '../user-table-toolbar';
import UserTableFiltersResult from '../user-table-filters-result';

// ----------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'deactivated', label: 'Deactivated' },
  { value: 'restricted', label: 'Restricted' },
];

const TABLE_HEAD = [
  { id: 'full_name', label: 'Name' },
  { id: 'phone_number', label: 'Phone Number', width: 180 },
  { id: 'date_joined', label: 'Joined At', width: 220 },
  { id: 'u_type', label: 'Role', width: 180 },
  { id: 'identity_verification_status', label: 'Verification Status', width: 100 },
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

export default function UserListView() {
  const table = useTable({
    defaultCurrentPage: 0,
    defaultRowsPerPage: 10,
  });
  const settings = useSettingsContext();
  const confirm = useBoolean();
  const downloadConfirm = useBoolean();

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

  const handleFilterStatus = useCallback(
    (event: React.SyntheticEvent, newValue: string) => {
      handleFilters('status', newValue);
    },
    [handleFilters]
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

  const getUserList = useCallback(async (data: any) => {
    try {
      const res = await getUsers(data);
      if(!res.success) throw res.data;
      setTableData(res.data);
      setTableMeta({ ...res.meta_data, user_status_count: res.user_status_count });
    } catch(err) {
      console.log(err);
    }
  }, []);

  useEffect(() => {
    getUserList({
      ...filters,
      stats: true,
      date_joined_after: filters.date_joined_after
        ? format(filters.date_joined_after, 'yyyy-MM-dd')
        : null,
      date_joined_before: filters.date_joined_before
        ? format(filters.date_joined_before, 'yyyy-MM-dd')
        : null,
      identity_verification_status: filters.identity_verification_status?.replace(
        'unverified',
        'not_verified'
      ),
      page_size: table.rowsPerPage,
      page: table.page + 1,
      status: filters.status === 'all' ? null : filters.status,
    });
  }, [filters, getUserList, table.page, table.rowsPerPage]);

  const handleVerify = async (userId: string, status: string) => {
    if(status === "verified") {
      try {
        console.log(userId, status);
        const res = await updateUser({
          id: userId,
          identity_status: "pending",
        });
        if(!res.success) throw res.data;
        getUserList({
          ...filters,
          stats: true,
          date_joined_after: filters.date_joined_after
            ? format(filters.date_joined_after, 'yyyy-MM-dd')
            : null,
          date_joined_before: filters.date_joined_before
            ? format(filters.date_joined_before, 'yyyy-MM-dd')
            : null,
          identity_verification_status: filters.identity_verification_status?.replace(
            'unverified',
            'not_verified'
          ),
          page_size: table.rowsPerPage,
          page: table.page + 1,
          status: filters.status === 'all' ? null : filters.status,
        })
      } catch(err) {
        console.log(err);
      }
    }
    else if(status === "not_verified" || status === "pending") {
      try {
        console.log(userId, status);
        const res = await updateUser({
          id: userId,
          identity_status: "verified",
        });
        if(!res.success) throw res.data;
        getUserList({
          ...filters,
          stats: true,
          date_joined_after: filters.date_joined_after
            ? format(filters.date_joined_after, 'yyyy-MM-dd')
            : null,
          date_joined_before: filters.date_joined_before
            ? format(filters.date_joined_before, 'yyyy-MM-dd')
            : null,
          identity_verification_status: filters.identity_verification_status?.replace(
            'unverified',
            'not_verified'
          ),
          page_size: table.rowsPerPage,
          page: table.page + 1,
          status: filters.status === 'all' ? null : filters.status,
        })
      } catch(err) {
        console.log(err);
      }
    }
  }

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
            links={[{ name: 'Dashboard', href: paths.dashboard.root }, { name: 'User List' }]}
            sx={{
              mb: { xs: 3, md: 5 },
            }}
          />
          <Button variant="contained" onClick={downloadConfirm.onTrue}>
            <Iconify icon="solar:download-bold" sx={{ marginRight: 1 }} /> Download
          </Button>
        </Stack>

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
                      (tab.value === 'active' && 'success') ||
                      (tab.value === 'deactivated' && 'warning') ||
                      (tab.value === 'restricted' && 'error') ||
                      'default'
                    }
                  >
                    {tab.value === 'all'
                      ? tableMeta.user_status_count?.reduce(
                        (acc: number, cur: any) => acc + cur.status_count,
                        0
                      )
                      : tableMeta?.user_status_count?.find(
                        (count: any) => count.status === tab.value
                      )?.status_count || 0}
                  </Label>
                }
              />
            ))}
          </Tabs>

          <UserTableToolbar filters={filters} onFilters={handleFilters} />

          {canReset && (
            <UserTableFiltersResult
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
                    <UserTableRow
                      key={row.id}
                      row={row}
                      selected={table.selected.includes(row.id)}
                      onSelectRow={() => table.onSelectRow(row.id)}
                      onDeleteRow={() => { }}
                      onEditRow={() => { }}
                      onVerify={() => handleVerify(row.id, row.identity_verification_status)}
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
              handleDownload();
              downloadConfirm.onFalse();
            }}
          >
            Download
          </Button>
        }
      />
    </>
  );
}
