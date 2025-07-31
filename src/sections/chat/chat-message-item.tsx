/* eslint-disable no-nested-ternary */
import { format } from 'date-fns';
// @mui
import Stack from '@mui/material/Stack';
import Avatar from '@mui/material/Avatar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
// types
import { IChatMessage } from 'src/types/chat';
import { useCallback } from 'react';
//
import { getBooking } from 'src/utils/queries/bookings';
import { UseBooleanReturnType } from 'src/hooks/use-boolean';
import { useGetMessage } from './hooks';

// ----------------------------------------------------------------------

type Props = {
  message: any;
  setChatDetails: Function;
  showDetails: UseBooleanReturnType;
};

export default function ChatMessageItem({ message, setChatDetails, showDetails }: Props) {
  const { me, senderDetails } = useGetMessage({
    message,
  });

  const { full_name, image } = senderDetails;
  const { content, created_at, m_type, meta } = message;

  console.log("content", content);

  const handleDetailsClick = useCallback(async () => {
    try {
      showDetails.onTrue();
      if(meta?.booking?.invoice_no) {
        const res = await getBooking(meta?.booking?.id);
        if(!res.success) throw res.data;
        setChatDetails(res.data);
      } else {
        setChatDetails(meta?.booking);
      }
    } catch(err) {
      console.log(err);
    }
  }, [meta, setChatDetails, showDetails]);

  const renderInfo = (
    <Typography
      noWrap
      variant="caption"
      sx={{
        mb: 1,
        color: 'text.disabled',
        ...(!me && {
          mr: 'auto',
        }),
      }}
    >
      {!me && `${full_name},`} &nbsp;
      {format(new Date(created_at), 'hh:mm aa')}
    </Typography>
  );

  const parsedFunction = () => {
    try {
      const item = content[0]?.trim();
      if(item?.startsWith('{') && item.endsWith('}')) {
        return JSON.parse(item);
      }
      return item;
    } catch(e) {
      return content[0];
    }
  };


  const renderBody = (content as string[]).map((msg, idx) => (
    <Stack
      key={idx}
      sx={{
        p: 1.5,
        minWidth: 48,
        display: 'flex',
        flexDirection: 'row',
        maxWidth: m_type === 'normal' ? 320 : '100%',
        borderRadius: 1,
        typography: 'body2',
        bgcolor: m_type === 'date' ? '' : 'background.neutral',
        ...(me && {
          color: 'grey.800',
          bgcolor: 'primary.lighter',
        }),
      }}
    >
      {(() => {
        const parsed = parsedFunction();

        if(typeof parsed === 'object') {
          return (
            <Box
              sx={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                width: '100%',
              }}
            >
              {/* Bottom-right link */}
              <Box
                component="a"
                href={`https://stayverz.divergenttechbd.com/rooms/${parsed.property_id}`}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  position: 'absolute',
                  bottom: 0,
                  right: 0,
                  fontSize: '12px',
                  color: 'primary.main',
                  textDecoration: 'underline',
                  cursor: 'pointer',
                }}
              >
                Visit
              </Box>

              {/* Image */}
              <Box
                component="img"
                src={parsed.image}
                alt="Preview"
                sx={{
                  width: 64,
                  height: 64,
                  borderRadius: 1,
                  objectFit: 'cover',
                }}
              />

              {/* Vertical Divider */}
              <Divider
                orientation="vertical"
                flexItem
                sx={{
                  width: '2px',
                  height: 48,
                  bgcolor: 'grey.400',
                  borderRadius: '999px',
                }}
              />

              {/* Message and Cost */}
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Typography sx={{ fontWeight: 500 }}>{parsed.message}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {parsed.cost}
                </Typography>
              </Box>
            </Box>
          );
        }

        return parsed;
      })()}


      {m_type === 'system' && (
        <Typography
          variant="button"
          sx={{ marginLeft: 1, cursor: 'pointer' }}
          onClick={handleDetailsClick}
        >
          Show Details
        </Typography>
      )}
    </Stack>
  ));



  return (
    <Stack
      direction="row"
      justifyContent={
        m_type === 'system' || m_type === 'date' ? 'center' : me ? 'flex-end' : 'unset'
      }
      sx={{ mb: 5 }}
    >
      {!me && m_type === 'normal' && (
        <Avatar alt={full_name} src={image} sx={{ width: 32, height: 32, mr: 2 }} />
      )}

      <Stack alignItems="flex-start">
        {m_type === 'normal' ? renderInfo : null}

        <Stack
          direction="column"
          sx={{
            '&:hover': {
              '& .message-actions': {
                opacity: 1,
              },
            },
            gap: 1,
          }}
        >

          {/* {parsedData ?
            <Avatar alt="" src={parsedData?.image} sx={{ width: 10, height: 10 }} />
            : ""
          } */}
          {/* 
          {parsedData ?
            <div className='w-fit shadow-[0px_1px_4px_0px_rgba(0,0,0,0.25)] rounded-lg py-3 px-3'>
              <div className='relative flex items-center gap-3 justify-between '>
                <div className='h-24 w-32'>
                  <picture>
                    <img src={parsedData?.image} className='w-full h-full object-cover rounded-md' alt='' />
                  </picture>
                </div>
                <Avatar alt="" src={parsedData?.image} variant="rounded" />

                <div className='h-16 border-2 border-[#F15925] rounded-full' />
                <div className='space-y-1 text-sm'>
                  <p className='font-semibold pe-4'>{parsedData?.message}</p>
                  <p>Price: {parsedData?.cost}</p>
                </div>
                <a
                  href={`https://stayverz.divergenttechbd.com/rooms/${parsedData?.property_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute text-sm text-[#F15925] font-semibold cursor-pointer -right-1.5 -bottom-1.5"
                >
                  View Details
                </a>
              </div>
            </div>
            : ""
          } */}
          {renderBody}

        </Stack>
      </Stack>
    </Stack>
  );
}
