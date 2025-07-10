// @mui
import TableRow from '@mui/material/TableRow';
import TableCell from '@mui/material/TableCell';
// hooks
import { useRouter } from 'src/routes/hook';
import { Link } from '@mui/material';
import { paths } from 'src/routes/paths';
//

type Props = {
  row: any;
};

export default function HostTableRow({ row }: Props) {
  const { total_property, total_sell_amount, first_name, last_name, id } = row;

  return (
    <TableRow hover>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <Link href={`${paths.dashboard.user.root}/${id}/edit`}>
          {first_name} {last_name}
        </Link>
      </TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>{total_property}</TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>৳ {total_sell_amount?.toFixed(2)}</TableCell>
    </TableRow>
  );
}
