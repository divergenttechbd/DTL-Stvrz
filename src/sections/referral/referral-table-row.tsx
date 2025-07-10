// @mui
import Button from '@mui/material/Button';
import Avatar from '@mui/material/Avatar';
import Tooltip from '@mui/material/Tooltip';
import TableRow from '@mui/material/TableRow';
import Checkbox from '@mui/material/Checkbox';
import TableCell from '@mui/material/TableCell';
import IconButton from '@mui/material/IconButton';
import ListItemText from '@mui/material/ListItemText';
// hooks
import { useBoolean } from 'src/hooks/use-boolean';
import { paths } from 'src/routes/paths';
// types
import { IUserItem } from 'src/types/user';
// components
import Label from 'src/components/label';
import Iconify from 'src/components/iconify';
import { ConfirmDialog } from 'src/components/custom-dialog';
import { useRouter } from 'src/routes/hook';
import _ from 'lodash';
import { format } from 'date-fns';
import MenuItem from '@mui/material/MenuItem';
import { Link } from '@mui/material';
import Box from '@mui/material/Box';
//

type Props = {
  selected: boolean;
  onEditRow: VoidFunction;
  // row: IUserItem;
  row: any;
  onSelectRow: VoidFunction;
  onDeleteRow: VoidFunction;
};

export default function ReferralTableRow({
  row,
  selected,
  onEditRow,
  onSelectRow,
  onDeleteRow,
}: Props) {
  const {
    id,
    username,
    u_type,
    full_name,
    email,
    total_host_referrals_made,
    total_host_referrals_successful,
    total_host_referral_earnings,
    total_guest_referrals_made,
    total_guest_referrals_successful,
    total_guest_referral_points,
  } = row;

  const confirm = useBoolean();

  const router = useRouter();

  return (
    <>
      <TableRow hover selected={selected}>
        <TableCell sx={{ alignContent: 'center' }}>#</TableCell>
        <TableCell sx={{ whiteSpace: 'nowrap' }}>
          <ListItemText
            primary={
              <Link href={`${paths.dashboard.user.root}/${id}/edit`}>{full_name}</Link>
            }
            // primary={full_name}
            secondary={username.split("_")[0]}
            primaryTypographyProps={{ typography: 'body2' }}
            secondaryTypographyProps={{ component: 'span', color: 'text.disabled' }}
          />
        </TableCell>
        <TableCell sx={{ whiteSpace: 'nowrap' }}>{u_type}</TableCell>
        {/* <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_host_referrals_made}</TableCell> */}
        <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_host_referrals_successful}</TableCell>
        <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_host_referral_earnings}</TableCell>
        {/* <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_guest_referrals_made}</TableCell> */}
        <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_guest_referrals_successful}</TableCell>
        <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_guest_referral_points}</TableCell>
        {/* <TableCell sx={{ whiteSpace: 'nowrap' }}>
          <Button
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'center' }}

          >
            <Iconify icon="solar:eye-bold" />
            <Box>View</Box>
          </Button>
        </TableCell> */}
      </TableRow>

      <ConfirmDialog
        open={confirm.value}
        onClose={confirm.onFalse}
        title="Delete"
        content="Are you sure want to delete?"
        action={
          <Button variant="contained" color="error" onClick={onDeleteRow}>
            Delete
          </Button>
        }
      />
    </>
  );
}
