import { Helmet } from 'react-helmet-async';
// routes
import { useParams } from 'src/routes/hook';
// sections
import { UserEditView } from 'src/sections/user/view';
import Button from '@mui/material/Button'
import { RouterLink } from 'src/routes/components'
import { paths } from 'src/routes/paths'
import Iconify from 'src/components/iconify'
import Stack from '@mui/material/Stack';

// ----------------------------------------------------------------------

export default function UserEditPage() {
  const params = useParams();

  const { id } = params;

  return (
    <>
      <Helmet>
        <title> Dashboard: User Edit</title>
      </Helmet>
      <UserEditView id={`${id}`} />
    </>
  );
}
