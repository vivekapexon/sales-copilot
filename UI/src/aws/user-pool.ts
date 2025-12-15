import { CognitoUserPool } from 'amazon-cognito-identity-js';
const poolData = {
 UserPoolId: 'us-east-1_pYh9EG8us',
 ClientId: '4r1qou4d7s8637rg9odrkpf9sf',
};
export const userPool = new CognitoUserPool(poolData);