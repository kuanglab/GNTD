import torch
import numpy as np
import torch.nn.functional as F

from NTD import NTD
from tqdm import tqdm
from sklearn.model_selection import ShuffleSplit
from utils import MSE, MAE, RMSE, MAPE, R2, generate_graph_Laplacian

class GNTD():
    
    # Initialization
    def __init__(self, expr_tensor, A_g, A_xy, rank, l):
        
        '''
        expr_tensor: expression tensor
        A_g: adjacency matrix of PPI graph
        A_xy: adjacency matrix of spatial graph
        rank: tensor rank
        l: weight on Cartesian product graph Laplacian regularization
        '''
        
        # Model parameters
        self.rank = rank
        self.l = l
        
        self.n_g, self.n_x, self.n_y = expr_tensor.shape
        self.expr_tensor = expr_tensor
        
        # Compute graph Laplacian for both PPI and spatial graphs
        self.L_g, self.L_xy = [generate_graph_Laplacian(A) for A in [A_g, A_xy]]
        
    
    # Generate index and value pairs for training and validation sets to select GNTD model
    def __training_valiation_split(self, ratio=0.1, random_state=1234567):
        
        '''
        ratio: the proportion of entries in the tensor used for validation
        '''
        
        index = self.expr_tensor.indices().numpy().T
        # Construct random permutation generator
        ss = ShuffleSplit(n_splits=1, test_size=ratio, random_state=random_state)
        training_index, validation_index = next(ss.split(X=index))
        
        training_expr = self.expr_tensor.values()[training_index]
        training_index = self.expr_tensor.indices()[:, training_index]
        training_index = training_index[0, :]*self.n_x*self.n_y + training_index[1, :]*self.n_y + training_index[2, :]
        
        validation_expr = self.expr_tensor.values()[validation_index]
        validation_index = self.expr_tensor.indices()[:, validation_index]
        validation_index = validation_index[0, :]*self.n_x*self.n_y + validation_index[1, :]*self.n_y + validation_index[2, :]
        
        return training_expr, training_index, validation_expr, validation_index
        
    def __train(self, expr, index, x_index, y_index, g_index):
        
        self.model.train()
        self.optimizer.zero_grad()
        
        expr = expr.to(self.device, dtype=torch.float32)
        x, y, g, expr_tensor_hat = self.model(x_index, y_index, g_index)
        expr_hat = torch.flatten(expr_tensor_hat)
        expr_hat = expr_hat[index].squeeze(-1)

        # Recontruction loss
        loss = F.mse_loss(expr, expr_hat, reduction="sum")

        # Cartesian product graph Laplacian regularization
        gTLg = torch.matmul(torch.matmul(g.t(), self.L_g.to(self.device)), g)
        gTg = torch.matmul(g.t(), g)
        xTx = torch.matmul(x.t(), x)
        yTy = torch.matmul(y.t(), y)
        xy = torch.kron(x, torch.ones(y.size(dim=0), 1).to(self.device)) * torch.kron(torch.ones(x.size(dim=0), 1).to(self.device), y)
        xyTLxy = torch.matmul(torch.matmul(xy.t(), self.L_xy.to(self.device)), xy)

        # Total loss
        loss += self.l*torch.sum(gTLg*xTx*yTy + gTg*xyTLxy)

        loss.backward()
        self.optimizer.step()

        return float(loss)
        
    @torch.no_grad()
    def __validate(self, expr, index, x_index, y_index, g_index):
        
        self.model.eval()
        
        _, _, _, expr_tensor_hat = self.model(x_index, y_index, g_index)
        expr_hat = torch.flatten(expr_tensor_hat)
        expr_hat = expr_hat[index].squeeze(-1)
        expr_hat = expr_hat.cpu()

        expr = expr.numpy()
        expr_hat = expr_hat.numpy()
        mse = MSE(expr, expr_hat)
        mae = MAE(expr, expr_hat)
        rmse = RMSE(expr, expr_hat)
        mape = MAPE(expr, expr_hat)
        r2 = R2(expr, expr_hat)

        return mse, mae, rmse, mape, r2
    
    @torch.no_grad()
    def __test(self, x_index, y_index, g_index):
        
        self.model.eval()
        
        _, _, _, expr_tensor_hat = self.model(x_index, y_index, g_index)
        expr_tensor_hat = expr_tensor_hat.cpu()

        return expr_tensor_hat
        
    def impute(self, lr=0.05, max_epoch=3000, verbose=True):
        
        '''
        lr: learning rate
        max_epoch: number of maximum epochs
        '''
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.lr = lr
        self.max_epoch = max_epoch
        self.verbose = verbose
        
        g_index = torch.arange(self.n_g, dtype=torch.long).to(self.device)
        x_index = torch.arange(self.n_x, dtype=torch.long).to(self.device)
        y_index = torch.arange(self.n_y, dtype=torch.long).to(self.device)
        
        training_expr, training_index, validation_expr, validation_index = self.__training_valiation_split()
        
        self.model = NTD(self.n_x, self.n_y, self.n_g, self.rank).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        
        # Print core model structure
        if self.verbose:
            print(self.model)

        # Model selection
        checkpoint = "./best_checkpoint.pt"
        
        pbar = tqdm(range(self.max_epoch))
        
        best_mse = np.Inf
        for epoch in pbar:
            
            pbar.set_description(f"epoch {epoch+1}")
            
            loss = self.__train(training_expr, training_index, x_index, y_index, g_index)
            mse, mae, rmse, mape, r2 = self.__validate(validation_expr, validation_index, x_index, y_index, g_index)
            
            if verbose:
                pbar.set_postfix({'loss': loss, 'val_mse': mse})
                
            # Save checkpoint
            if mse < best_mse:
                best_mse = mse
                torch.save(self.model.state_dict(), checkpoint)
                
            pbar.update(1)
            
        pbar.close()

        # Output imputation
        self.model.load_state_dict(torch.load(checkpoint))
        expr_tensor_hat = self.__test(x_index, y_index, g_index)
        self.expr_tensor_hat = expr_tensor_hat
        
        return expr_tensor_hat
    
    def to_numpy(self):
        
        return self.expr_tensor_hat.numpy()
        
    