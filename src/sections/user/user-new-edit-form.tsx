import LoadingButton from '@mui/lab/LoadingButton'
import { Alert, Avatar, Dialog, DialogContent, TextField } from '@mui/material'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import Snackbar from '@mui/material/Snackbar'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import Typography from '@mui/material/Typography'
import Grid from '@mui/material/Unstable_Grid2'
import startCase from 'lodash/startCase'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { ConfirmDialog } from 'src/components/custom-dialog'
import Label from 'src/components/label'
import { IUserItem } from 'src/types/user'
import { updateUser } from 'src/utils/queries/users'

type Props = {
  currentUser?: IUserItem;
  getUserDetails?: Function;
};

export default function UserNewEditForm({ currentUser, getUserDetails }: Props) {
  // console.log('currentUser', currentUser);
  const [open, setOpen] = useState(false);
  const [selectedImage, setSelectedImage] = useState('');
  const [verificationAction, setVerificationAction] = useState<'' | 'verified' | 'rejected'>('');
  const [reason, setReason] = useState<string>('');
  const [snackbarOpen, setSnackbarOpen] = useState(false);

  const { handleSubmit, register, reset } = useForm({
    defaultValues: {
      first_name: currentUser?.first_name,
      last_name: currentUser?.last_name,
      email: currentUser?.email,
    },
  });

  const onSubmit = async (data: any) => {
    try {
      const res = await updateUser({
        id: currentUser?.id,
        first_name: data?.first_name,
        last_name: data?.last_name,
        user_status: currentUser?.status,
        email: data?.email,
      });
      console.log('response', res)
      if(!res.success) throw res.data;
      getUserDetails?.();
      setVerificationAction('');
      setSnackbarOpen(true);
    } catch(err) {
      console.log(err);
    }
  };

  useEffect(() => {
    reset(currentUser);
  }, [reset, currentUser]);

  const handleVerificationAction = useCallback(
    (action: '' | 'verified' | 'rejected') => () => {
      setVerificationAction(action);
    },
    []
  );

  const confirmVerification = useCallback(async () => {
    try {
      const res = await updateUser({
        id: currentUser?.id,
        identity_status: verificationAction,
        reject_reason: verificationAction === 'rejected' ? reason : '',
      });
      if(!res.success) throw res.data;
      getUserDetails?.();
      setVerificationAction('');
    } catch(err) {
      console.log(err);
    }
  }, [currentUser?.id, getUserDetails, reason, verificationAction]);

  const toggleUserStatus = useCallback(async () => {
    try {
      const res = await updateUser({
        id: currentUser?.id,
        user_status: currentUser?.status === 'active' ? 'restricted' : 'active',
      });
      if(!res.success) throw res.data;
      getUserDetails?.();
      setVerificationAction('');
    } catch(err) {
      console.log(err);
    }
  }, [currentUser?.id, currentUser?.status, getUserDetails]);

  const handleClickOpen = useCallback(
    (imageUrl: string) => () => {
      setSelectedImage(imageUrl);
      setOpen(true);
    },
    []
  );

  const handleClose = useCallback(() => {
    setOpen(false);
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-shadow
  const handleSnackbarClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if(reason === 'clickaway') {
      return;
    }

    setSnackbarOpen(false);
  };
  return (
    <Grid container spacing={3}>
      <Grid xs={12} md={4}>
        <Card sx={{ pt: 10, pb: 5, px: 3 }}>
          {currentUser && (
            <Label
              color={
                (currentUser?.identity_verification_status === 'pending' && 'warning') ||
                (currentUser?.identity_verification_status === 'verified' && 'success') ||
                (currentUser?.identity_verification_status === 'rejected' && 'error') ||
                'warning'
              }
              sx={{ position: 'absolute', top: 24, right: 24 }}
            >
              {currentUser?.identity_verification_status}
            </Label>
          )}

          <Stack sx={{ width: '100%' }}>
            <Avatar
              src={currentUser?.image}
              sx={{
                bgcolor: 'background.neutral',
                width: 150,
                height: 150,
                margin: 'auto',
                marginBottom: '2rem',
              }}
            />
          </Stack>
          {currentUser && (
            <Stack sx={{ textAlign: 'center' }}>
              <Typography variant="body1">
                {currentUser.full_name} ({startCase(currentUser.u_type)})
              </Typography>
              <Typography variant="body1" sx={{ my: 1 }}>
                +88 {currentUser.phone_number}
              </Typography>
              {currentUser?.profile?.languages?.length && (
                <Typography variant="subtitle2">
                  Speaks: {currentUser?.profile.languages.join(', ')}
                </Typography>
              )}
              <Typography variant="subtitle2" sx={{ my: 1 }}>
                {currentUser?.profile?.bio}
              </Typography>
            </Stack>
          )}

          {currentUser && (
            <Stack
              sx={{
                display: 'flex',
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Switch checked={currentUser?.status === 'restricted'} onChange={toggleUserStatus} />
              <Typography variant="subtitle1">Ban This User</Typography>
            </Stack>
          )}
        </Card>
      </Grid>

      <Grid xs={12} md={8}>
        <Card sx={{ p: 3 }}>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Box
              rowGap={3}
              columnGap={2}
              display="grid"
              gridTemplateColumns={{
                xs: 'repeat(1, 1fr)',
                sm: 'repeat(2, 1fr)',
              }}
            >
              <TextField
                label="First Name"
                {...register('first_name')}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                label="Last Name"
                {...register('last_name')}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                // name="email"
                label="Email Address"
                {...register('email')}
                // InputProps={{
                //   readOnly: true,
                // }}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                name="phone_number"
                label="Phone Number"
                value={currentUser?.phone_number || ''}
                InputProps={{
                  readOnly: true,
                }}
              />
              <TextField
                name="u_type"
                label="Role"
                value={currentUser?.u_type || ''}
                InputProps={{
                  readOnly: true,
                }}
              />
            </Box>
            <LoadingButton type="submit" variant="contained" color="primary" sx={{ mt: 3 }}>
              Update Details
            </LoadingButton>
          </form>


          {currentUser?.identity_verification_images?.front_image && (
            <Typography variant="body1" sx={{ marginTop: '1rem' }}>
              Verification &nbsp;
              <b>({startCase(currentUser?.identity_verification_method?.split('_').join(' '))})</b>
            </Typography>
          )}
          <Box
            rowGap={3}
            columnGap={2}
            display="grid"
            gridTemplateColumns={{
              xs: 'repeat(1, 1fr)',
              sm: 'repeat(2, 1fr)',
            }}
          >
            {currentUser?.identity_verification_images?.front_image && (
              <Button
                onClick={handleClickOpen(currentUser?.identity_verification_images?.front_image)}
              >
                <img
                  src={currentUser?.identity_verification_images?.front_image}
                  alt="Front"
                  style={{ cursor: 'pointer', width: '100%' }}
                />
              </Button>
            )}
            {currentUser?.identity_verification_images?.back_image && (
              <Button
                onClick={handleClickOpen(currentUser?.identity_verification_images?.back_image)}
              >
                <img
                  src={currentUser?.identity_verification_images?.back_image}
                  alt="Back"
                  style={{ cursor: 'pointer', width: '100%' }}
                />
              </Button>
            )}
          </Box>


          {/* Live Verification Photo */}
          {currentUser?.identity_verification_method === "live" && (
            <Typography variant="body1" sx={{ marginTop: '1rem' }}>
              Verification &nbsp;
              <b>({startCase(currentUser?.identity_verification_method?.split('_').join(' '))})</b>
            </Typography>
          )}

          <>
            {/* First image full width */}
            {currentUser?.identity_verification_method === "live" &&
              currentUser?.identity_verification_images?.live && (() => {
                const images = currentUser.identity_verification_images.live.split(",");
                const firstImage = images[0];
                const restImages = images.slice(1);

                return (
                  <>
                    {/* Show first image separately on top */}
                    <Box mb={3}>
                      <Button onClick={handleClickOpen(firstImage)}>
                        <img
                          src={firstImage}
                          alt="identity-0"
                          style={{
                            cursor: "pointer",
                            width: "100%",
                            height: "440px",
                            borderRadius: "8px",
                          }}
                        />
                      </Button>
                    </Box>

                    {/* Show rest of the images in a grid */}
                    <Box
                      rowGap={3}
                      columnGap={2}
                      display="grid"
                      gridTemplateColumns={{
                        xs: "repeat(1, 1fr)",
                        sm: "repeat(2, 1fr)",
                      }}
                    >
                      {restImages.map((url, index) => (
                        <Button key={index + 1} onClick={handleClickOpen(url)}>
                          <img
                            src={url}
                            alt={`identity-${index + 1}`}
                            style={{
                              cursor: "pointer",
                              width: "100%",
                              borderRadius: "8px",
                            }}
                          />
                        </Button>
                      ))}
                    </Box>
                  </>
                );
              })()}
          </>


          {/* Live Verification Photo */}


          {currentUser?.identity_verification_status === 'pending' && (
            <Stack
              sx={{
                display: 'flex',
                flexDirection: 'row',
                mt: 3,
                justifyContent: 'flex-end',
                gap: 1,
              }}
              alignItems="flex-end"
            >
              <LoadingButton
                type="submit"
                variant="contained"
                color="error"
                onClick={handleVerificationAction('rejected')}
              >
                Reject
              </LoadingButton>
              <LoadingButton
                type="submit"
                variant="contained"
                color="inherit"
                onClick={handleVerificationAction('verified')}
              >
                Accept
              </LoadingButton>
            </Stack>
          )}
        </Card>
      </Grid>

      <ConfirmDialog
        open={verificationAction !== ''}
        onClose={handleVerificationAction('')}
        title="Verification Action"
        content={
          <>
            Are you sure want to{' '}
            {verificationAction === 'rejected' ? 'reject this verification?' : 'verify this user?'}
            {verificationAction === 'rejected' && (
              <TextField
                sx={{ width: '100%', mt: 2 }}
                label="Rejection reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            )}
          </>
        }
        action={
          <Button variant="contained" color="primary" onClick={confirmVerification}>
            Confirm
          </Button>
        }
      />

      <Dialog open={open} onClose={handleClose}>
        <DialogContent sx={{ padding: 0 }}>
          <img src={selectedImage} alt="Selected" style={{ width: '100%' }} />
        </DialogContent>
      </Dialog>

      <Snackbar
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        open={snackbarOpen}
        autoHideDuration={3000}
        message=""
        onClose={handleSnackbarClose}
      >
        <Alert
          severity="success"
          variant="filled"
          sx={{ width: '100%' }}
        >
          User info updated!
        </Alert>
      </Snackbar>
    </Grid>
  );
}
