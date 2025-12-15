
// const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT || 'https://cz4nknxebz2pvetjcag2r7gqva0bpkqy.lambda-url.us-east-1.on.aws/';

const ACCESS_KEY = import.meta.env.VITE_ACCESS_KEY||'';
const SECRET_KEY = import.meta.env.VITE_SECRET_KEY||'';

export const config = {
    // AWS_ACCESS_KEY_ID :ACCESS_KEY,
    // AWS_SECRET_ACCESS_KEY : SECRET_KEY,
    region: "us-east-1",
    credentials: {
    accessKeyId: ACCESS_KEY,   // replace with your actual access key
    secretAccessKey: SECRET_KEY,
    // sessionToken: "YOUR_SESSION_TOKEN",  // if using temporary credentials
  } 

}